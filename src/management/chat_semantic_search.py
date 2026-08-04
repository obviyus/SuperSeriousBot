import asyncio
import time
from dataclasses import dataclass
from itertools import groupby

import ai
import pydantic

from chat_search_config import (
    ANSWER_EVIDENCE_COUNT,
    AUTHOR_VECTOR_RESULT_COUNT,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    QUERY_INSTRUCTION,
    VECTOR_RESULT_COUNT,
)
from commands.ai import generate_object
from config.db import TursoRow, get_db
from config.logger import logger
from management.chat_search_cache import open_search_cache
from management.chat_search_index import format_author
from openrouter_embeddings import openrouter_embeddings, vector32_json

NO_SOLID_ANSWER = "No solid answer in the chat."


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


class SearchAnswerOutput(pydantic.BaseModel):
    answer: str = pydantic.Field(
        description="One to three sentence answer without citation markers."
    )
    citations: list[int] = pydantic.Field(
        description="Evidence numbers that directly support every claim in the answer."
    )


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
            "Answer from the supplied Telegram chat evidence only. Keep the answer "
            "to one to three sentences and preserve participants' @handles exactly. "
            "Every claim must be directly supported by the evidence numbers returned "
            "in citations. Respect who said each message and who they addressed. Do "
            "not turn a statement about someone into a fact about its speaker. Answer "
            "the question exactly as asked: if it names a participant, never replace "
            "them with a different participant. Factual superlatives and quantitative "
            "comparisons require evidence that establishes the comparison, not merely "
            "related conversation. Subjective and hypothetical questions may infer "
            "from observed chat behavior; the evidence need not use the question's "
            "exact label. When asked why a named participant has a subjective label, "
            "answer with cited behavior that fits the label whenever it is available. "
            "For subjective questions, use the no-answer result only when there is no "
            "relevant behavior about the requested participant or candidates. "
            "Choose an answer when relevant behavior supports one, then explain only "
            "that cited behavior. Never invent events or attributes. Put no citation "
            "markers, message IDs, or URLs in answer. If the evidence does "
            f"not support a solid answer, return '{NO_SOLID_ANSWER}' with no citations."
        ),
        ai.user_message(f"Question: {query}\n\nEvidence:\n{evidence_text}"),
    ]


async def answer_from_evidence(
    query: str,
    evidence: list[SearchEvidence],
) -> SearchAnswerOutput:
    return await generate_object(
        "search",
        answer_messages(query, evidence),
        SearchAnswerOutput,
        extra_body={"reasoning": {"effort": "low"}},
    )


def render_search_answer(
    output: SearchAnswerOutput, evidence: list[SearchEvidence]
) -> str:
    answer = output.answer.strip()
    if not answer or answer == NO_SOLID_ANSWER:
        return NO_SOLID_ANSWER

    citations = []
    for index in dict.fromkeys(output.citations):
        if not 1 <= index <= len(evidence):
            continue
        item = evidence[index - 1]
        if link := telegram_message_link(item.chat_id, item.citation_message_id):
            citations.append(f"[{index}]({link})")

    if not citations:
        return NO_SOLID_ANSWER
    return f"{answer}\n\n{' '.join(citations)}"


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
    output = await answer_from_evidence(query, evidence)
    answer = render_search_answer(output, evidence)
    answered = time.monotonic()
    logger.info(
        "Semantic search timings: chat_id=%s embedding_ms=%d retrieval_ms=%d "
        "answer_ms=%d evidence_ranges=%s citations=%s grounded=%s",
        chat_id,
        round((embedded - started) * 1000),
        round((retrieved - embedded) * 1000),
        round((answered - retrieved) * 1000),
        [(item.start_message_id, item.end_message_id) for item in evidence],
        output.citations,
        answer != NO_SOLID_ANSWER,
    )
    return answer
