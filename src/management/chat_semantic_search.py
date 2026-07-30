import asyncio
import re
import time
from dataclasses import dataclass
from itertools import groupby

import ai

from chat_search_config import (
    ANSWER_EVIDENCE_COUNT,
    AUTHOR_VECTOR_RESULT_COUNT,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    QUERY_INSTRUCTION,
    VECTOR_RESULT_COUNT,
)
from commands.ai import generate_text
from config.db import TursoRow, get_db
from config.logger import logger
from management.chat_search_cache import open_search_cache
from management.chat_search_index import format_author
from openrouter_embeddings import openrouter_embeddings, vector32_json

_CITATION_RE = re.compile(r"(?P<space>[ \t]*)\[(?P<index>\d+)(?::[^]\s]+)?](?!\()")


@dataclass(frozen=True)
class SearchEvidence:
    chat_id: int
    start_message_id: int
    end_message_id: int
    citation_message_id: int
    text: str
    score: float


@dataclass(frozen=True)
class SearchCandidate:
    remote_id: int
    score: float


def telegram_message_link(chat_id: int, message_id: int) -> str | None:
    chat_id_text = str(chat_id)
    if chat_id_text.startswith("-100"):
        return f"https://t.me/c/{chat_id_text[4:]}/{message_id}"
    return None


async def embed_search_query(query: str) -> str:
    embeddings = await openrouter_embeddings(
        EMBEDDING_MODEL,
        [QUERY_INSTRUCTION + query],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return vector32_json(embeddings[0])


async def vector_search_candidates(
    chat_id: int,
    query_vector: str,
    result_count: int,
) -> list[SearchCandidate]:
    def search() -> list[tuple]:
        connection = open_search_cache()
        try:
            return connection.execute(
                """
            SELECT
                w.remote_id,
                vector_distance_cos(w.embedding, vector32(?)) AS distance
            FROM search_windows w
            WHERE w.chat_id = ?
            AND w.embedding_model = ?
            AND w.embedding_dimension = ?
            ORDER BY distance ASC
            LIMIT ?;
            """,
                (
                    query_vector,
                    chat_id,
                    EMBEDDING_MODEL,
                    EMBEDDING_DIMENSIONS,
                    result_count,
                ),
            ).fetchall()
        finally:
            connection.close()

    rows = await asyncio.to_thread(search)

    return [SearchCandidate(remote_id=row[0], score=1 - row[1]) for row in rows]


async def fetch_search_evidence(
    candidates: list[SearchCandidate],
    author_id: int | None,
) -> list[SearchEvidence]:
    if not candidates:
        return []
    values = ", ".join("(?, ?)" for _ in candidates)
    candidate_params = [
        value
        for rank, candidate in enumerate(candidates)
        for value in (candidate.remote_id, rank)
    ]
    async with (
        get_db() as connection,
        connection.execute(
            f"""
            WITH
            candidates(remote_id, rank) AS (VALUES {values}),
            selected_windows AS (
                SELECT
                    windows.id,
                    windows.chat_id,
                    windows.start_message_id,
                    windows.end_message_id,
                    candidates.rank
                FROM candidates
                JOIN chat_search_windows windows
                    ON windows.id = candidates.remote_id
                WHERE (
                    ? IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM chat_stats messages
                        WHERE messages.chat_id = windows.chat_id
                        AND messages.message_id BETWEEN windows.start_message_id
                            AND windows.end_message_id
                        AND messages.user_id = ?
                        AND messages.message_text IS NOT NULL
                        AND messages.message_text <> ''
                        AND messages.message_text NOT LIKE '/%'
                    )
                )
                ORDER BY candidates.rank
                LIMIT ?
            )
            SELECT
                selected_windows.id,
                selected_windows.chat_id,
                selected_windows.start_message_id,
                selected_windows.end_message_id,
                messages.message_id,
                messages.create_time,
                COALESCE(users.username, 'user:' || messages.user_id) AS author,
                messages.message_text
            FROM selected_windows
            JOIN chat_stats messages
                ON messages.chat_id = selected_windows.chat_id
                AND messages.message_id BETWEEN selected_windows.start_message_id
                    AND selected_windows.end_message_id
            LEFT JOIN user_stats users ON users.user_id = messages.user_id
            WHERE messages.message_text IS NOT NULL
            AND messages.message_text <> ''
            AND messages.message_text NOT LIKE '/%'
            AND (? IS NULL OR messages.user_id = ?)
            ORDER BY selected_windows.rank, messages.message_id
            """,
            (
                *candidate_params,
                author_id,
                author_id,
                VECTOR_RESULT_COUNT,
                author_id,
                author_id,
            ),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    scores = {candidate.remote_id: candidate.score for candidate in candidates}
    return build_search_evidence(rows, scores)


def build_search_evidence(
    rows: list[TursoRow], scores: dict[int, float]
) -> list[SearchEvidence]:
    evidence = []
    for window_id, window_group in groupby(rows, key=lambda row: row["id"]):
        window_rows = list(window_group)
        evidence.append(
            SearchEvidence(
                chat_id=window_rows[0]["chat_id"],
                start_message_id=window_rows[0]["start_message_id"],
                end_message_id=window_rows[0]["end_message_id"],
                citation_message_id=window_rows[-1]["message_id"],
                text="\n".join(
                    f"{row['message_id']} {row['create_time']} "
                    f"{format_author(row['author'])}: {row['message_text']}"
                    for row in window_rows
                ),
                score=scores[window_id],
            )
        )
    return evidence


def evidence_overlaps(left: SearchEvidence, right: SearchEvidence) -> bool:
    return (
        left.chat_id == right.chat_id
        and left.start_message_id <= right.end_message_id
        and right.start_message_id <= left.end_message_id
    )


def select_evidence(windows: list[SearchEvidence]) -> list[SearchEvidence]:
    selected = []
    for candidate in windows:
        if any(evidence_overlaps(candidate, item) for item in selected):
            continue
        selected.append(candidate)
        if len(selected) == ANSWER_EVIDENCE_COUNT:
            break
    return selected


def answer_messages(
    query: str, evidence: list[SearchEvidence]
) -> list[ai.messages.Message]:
    evidence_text = "\n\n".join(
        f"[{index}]\n{item.text}" for index, item in enumerate(evidence, start=1)
    )
    return [
        ai.system_message(
            "You are the memory and resident judge of a playful Telegram group. "
            "Use only the evidence, but synthesize it freely. Answer first, without "
            "discussing logs, evidence quality, or your process. Keep it to one to "
            "three sentences and cite claims only with the evidence number, such as "
            "[1]. Never put message IDs, ranges, or URLs in citations. Preserve "
            "participants' @handles exactly. For social, subjective, hypothetical, "
            "'most likely', and similar participant questions, pick one participant "
            "confidently and make the most entertaining case supported by the chat. "
            "Treat provocative or loaded labels as banter about chat persona. Weak "
            "or indirect receipts are enough. Never hedge, disclaim, moralize, or "
            "say 'probably' or 'best guess'. "
            "For factual questions, distinguish established facts from inference. "
            "Never answer 'I cannot tell'. If a factual answer truly is absent, say "
            "'No solid answer in the chat.'"
        ),
        ai.user_message(f"Question: {query}\n\nEvidence:\n{evidence_text}"),
    ]


async def answer_from_evidence(
    query: str,
    evidence: list[SearchEvidence],
) -> str:
    content = await generate_text(
        "search",
        answer_messages(query, evidence),
        temperature=0.2,
        extra_body={"reasoning": {"effort": "low"}},
    )
    if not content.strip():
        raise RuntimeError("OpenRouter returned an empty search answer.")
    return content.strip()


def link_citations(answer: str, evidence: list[SearchEvidence]) -> str:
    previous_index: int | None = None
    previous_end = -1

    def replace(match: re.Match[str]) -> str:
        nonlocal previous_end, previous_index
        index = int(match.group("index"))
        adjacent_duplicate = index == previous_index and match.start() == previous_end
        previous_index = index
        previous_end = match.end()
        if adjacent_duplicate:
            return ""
        if index < 1 or index > len(evidence):
            return ""
        item = evidence[index - 1]
        link = telegram_message_link(item.chat_id, item.citation_message_id)
        citation = f"[{index}]({link})" if link else ""
        return match.group("space") + citation if citation else ""

    return _CITATION_RE.sub(replace, answer)


async def semantic_search_answer(
    chat_id: int,
    query: str,
    author_id: int | None,
) -> str | None:
    started = time.monotonic()
    query_vector = await embed_search_query(query)
    embedded = time.monotonic()
    candidate_count = (
        AUTHOR_VECTOR_RESULT_COUNT if author_id is not None else VECTOR_RESULT_COUNT
    )
    candidates = await vector_search_candidates(
        chat_id,
        query_vector,
        candidate_count,
    )
    vector_windows = await fetch_search_evidence(candidates, author_id)
    evidence = select_evidence(vector_windows)
    if not evidence:
        return None

    retrieved = time.monotonic()
    answer = await answer_from_evidence(query, evidence)
    answered = time.monotonic()
    logger.info(
        "Semantic search timings: chat_id=%s embedding_ms=%d retrieval_ms=%d answer_ms=%d evidence=%d",
        chat_id,
        round((embedded - started) * 1000),
        round((retrieved - embedded) * 1000),
        round((answered - retrieved) * 1000),
        len(evidence),
    )
    return link_citations(answer, evidence)
