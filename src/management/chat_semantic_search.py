import asyncio
import logging
import re
import time
from dataclasses import dataclass

import aiohttp

from chat_search_config import (
    ANSWER_EVIDENCE_COUNT,
    ANSWER_MODEL,
    AUTHOR_VECTOR_RESULT_COUNT,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    QUERY_INSTRUCTION,
    VECTOR_RESULT_COUNT,
)
from commands.ai import first_message_content
from config.db import get_db
from config.options import config
from management.chat_search_cache import open_search_cache
from openrouter_embeddings import (
    openrouter_api_headers,
    openrouter_embeddings,
    vector32_json,
)

_CITATION_RE = re.compile(r"\[(\d+)(?::(\d+))?]")


@dataclass(frozen=True)
class SearchEvidence:
    chat_id: int
    start_message_id: int
    end_message_id: int
    text: str
    score: float

    @property
    def citation_message_id(self) -> int:
        return self.end_message_id


@dataclass(frozen=True)
class SearchCandidate:
    remote_id: int
    score: float


def telegram_message_link(chat_id: int, message_id: int) -> str | None:
    chat_id_text = str(chat_id)
    if chat_id_text.startswith("-100"):
        return f"https://t.me/c/{chat_id_text[4:]}/{message_id}"
    return None


async def embed_search_query(session: aiohttp.ClientSession, query: str) -> str:
    embeddings = await openrouter_embeddings(
        session,
        config.API.OPENROUTER_API_KEY,
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
    async with get_db() as connection:
        async with connection.execute(
            f"""
            WITH candidates(remote_id, rank) AS (VALUES {values})
            SELECT
                windows.id,
                windows.chat_id,
                windows.start_message_id,
                windows.end_message_id,
                windows.message_text
            FROM candidates
            JOIN chat_search_windows windows ON windows.id = candidates.remote_id
            WHERE (
                ? IS NULL
                OR EXISTS (
                    SELECT 1
                    FROM chat_stats messages
                    WHERE messages.chat_id = windows.chat_id
                    AND messages.message_id BETWEEN windows.start_message_id
                        AND windows.end_message_id
                    AND messages.user_id = ?
                )
            )
            ORDER BY candidates.rank
            LIMIT ?
            """,
            (
                *candidate_params,
                author_id,
                author_id,
                VECTOR_RESULT_COUNT,
            ),
        ) as cursor:
            rows = await cursor.fetchall()
    scores = {candidate.remote_id: candidate.score for candidate in candidates}
    return [
        SearchEvidence(
            chat_id=row["chat_id"],
            start_message_id=row["start_message_id"],
            end_message_id=row["end_message_id"],
            text=row["message_text"],
            score=scores[row["id"]],
        )
        for row in rows
    ]


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
) -> list[dict[str, object]]:
    evidence_text = "\n\n".join(
        f"[{index}]\n{item.text}" for index, item in enumerate(evidence, start=1)
    )
    return [
        {
            "role": "system",
            "content": (
                "You are the memory of a playful Telegram group, not a fact-checker or "
                "auditor. Use only the evidence, but synthesize it freely. Answer first, "
                "without discussing logs, evidence quality, or your process. Keep it to "
                "one to three sentences and cite claims with the evidence number and exact "
                "message ID, such as [1:123456]. Preserve participants' @handles exactly. "
                "For social, subjective, hypothetical, "
                "'most likely', and similar participant questions, always make the most "
                "entertaining plausible choice supported by the chat. Weak or indirect "
                "receipts are enough; use 'probably' or 'best guess' only when useful. "
                "For factual questions, distinguish established facts from inference. "
                "Never answer 'I cannot tell'. If a factual answer truly is absent, say "
                "'No solid answer in the chat.'"
            ),
        },
        {
            "role": "user",
            "content": f"Question: {query}\n\nEvidence:\n{evidence_text}",
        },
    ]


async def answer_from_evidence(
    session: aiohttp.ClientSession,
    query: str,
    evidence: list[SearchEvidence],
) -> str:
    payload = {
        "model": ANSWER_MODEL,
        "messages": answer_messages(query, evidence),
        "temperature": 0.2,
        "max_tokens": 350,
    }
    async with session.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=openrouter_api_headers(config.API.OPENROUTER_API_KEY),
        json=payload,
        timeout=aiohttp.ClientTimeout(total=120),
    ) as response:
        response.raise_for_status()
        data = await response.json()

    content = first_message_content(data)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter returned an empty search answer.")
    usage = data.get("usage")
    if isinstance(usage, dict):
        logging.info(
            "Search answer usage: prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
    return content.strip()


def link_citations(answer: str, evidence: list[SearchEvidence]) -> str:
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index < 1 or index > len(evidence):
            return match.group(0)
        item = evidence[index - 1]
        message_id = int(match.group(2)) if match.group(2) else item.citation_message_id
        if not item.start_message_id <= message_id <= item.end_message_id:
            return match.group(0)
        link = telegram_message_link(item.chat_id, message_id)
        return f"[{index}]({link})" if link else match.group(0)

    return _CITATION_RE.sub(replace, answer)


async def semantic_search_answer(
    chat_id: int,
    query: str,
    author_id: int | None,
) -> str | None:
    started = time.monotonic()
    async with aiohttp.ClientSession() as session:
        query_vector = await embed_search_query(session, query)
        embedded = time.monotonic()
        candidate_count = (
            AUTHOR_VECTOR_RESULT_COUNT if author_id is not None else VECTOR_RESULT_COUNT
        )
        candidates = await vector_search_candidates(
            chat_id,
            query_vector,
            candidate_count,
        )
        vector_windows = await fetch_search_evidence(
            candidates,
            author_id,
        )
        evidence = select_evidence(vector_windows)
        if not evidence:
            return None

        retrieved = time.monotonic()
        answer = await answer_from_evidence(session, query, evidence)
        answered = time.monotonic()
        logging.info(
            "Semantic search timings: chat_id=%s embedding_ms=%d retrieval_ms=%d answer_ms=%d evidence=%d",
            chat_id,
            round((embedded - started) * 1000),
            round((retrieved - embedded) * 1000),
            round((answered - retrieved) * 1000),
            len(evidence),
        )
        return link_citations(answer, evidence)
