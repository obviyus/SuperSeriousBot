import re
from dataclasses import dataclass

import aiohttp

from chat_search_config import (
    ANSWER_EVIDENCE_COUNT,
    ANSWER_MODEL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    FTS_HIT_COUNT,
    QUERY_INSTRUCTION,
    VECTOR_RESULT_COUNT,
)
from commands.ai import first_message_content
from config.db import get_db
from config.options import config
from openrouter_embeddings import (
    openrouter_api_headers,
    openrouter_embeddings,
    vector32_json,
)

_TOKEN_RE = re.compile(r"[\w@]+", re.UNICODE)
_FTS_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "does",
    "do",
    "for",
    "have",
    "how",
    "is",
    "it",
    "of",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "who",
    "why",
}


@dataclass(frozen=True)
class ChatMessageText:
    message_id: int
    create_time: str
    author: str
    text: str


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


def build_fts_query(query: str) -> str:
    terms = []
    for token in _TOKEN_RE.findall(query.lower()):
        term = token.lstrip("@")
        if len(term) < 2 or term in _FTS_STOPWORDS:
            continue
        terms.append(term)
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(terms))


def telegram_message_link(chat_id: int, message_id: int) -> str | None:
    chat_id_text = str(chat_id)
    if chat_id_text.startswith("-100"):
        return f"https://t.me/c/{chat_id_text[4:]}/{message_id}"
    return None


def build_evidence_text(rows: list[ChatMessageText]) -> str:
    return "\n".join(
        f"{row.message_id} {row.create_time} {row.author}: {row.text}" for row in rows
    )


def format_author(author: object) -> str:
    author_text = str(author)
    return author_text if author_text.startswith("user:") else f"@{author_text}"


async def embed_search_query(session: aiohttp.ClientSession, query: str) -> str:
    embeddings = await openrouter_embeddings(
        session,
        config.API.OPENROUTER_API_KEY,
        EMBEDDING_MODEL,
        [QUERY_INSTRUCTION + query],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return vector32_json(embeddings[0])


async def vector_search_windows(
    chat_id: int,
    query_vector: str,
    author_id: int | None,
) -> list[SearchEvidence]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT
                w.chat_id,
                w.start_message_id,
                w.end_message_id,
                w.message_text,
                vector_distance_cos(w.embedding, vector32(?)) AS distance
            FROM chat_search_windows w
            WHERE w.chat_id = ?
            AND w.embedding_model = ?
            AND w.embedding_dimension = ?
            AND (
                ? IS NULL
                OR EXISTS (
                    SELECT 1
                    FROM chat_stats cs
                    WHERE cs.chat_id = w.chat_id
                    AND cs.message_id BETWEEN w.start_message_id AND w.end_message_id
                    AND cs.user_id = ?
                )
            )
            ORDER BY distance ASC
            LIMIT ?;
            """,
            (
                query_vector,
                chat_id,
                EMBEDDING_MODEL,
                EMBEDDING_DIMENSIONS,
                author_id,
                author_id,
                VECTOR_RESULT_COUNT,
            ),
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        SearchEvidence(
            chat_id=row["chat_id"],
            start_message_id=row["start_message_id"],
            end_message_id=row["end_message_id"],
            text=row["message_text"],
            score=1 - row["distance"],
        )
        for row in rows
    ]


async def fts_hit_message_ids(
    chat_id: int,
    query: str,
    author_id: int | None,
) -> list[int]:
    fts_query = build_fts_query(query)
    if not fts_query:
        return []

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT cs.message_id
            FROM chat_stats_fts csf
            INNER JOIN chat_stats cs ON cs.id = csf.rowid
            WHERE csf.message_text MATCH ?
            AND csf.chat_id = ?
            AND cs.message_id IS NOT NULL
            AND cs.message_text NOT LIKE '/%'
            AND (? IS NULL OR cs.user_id = ?)
            ORDER BY cs.create_time DESC
            LIMIT ?;
            """,
            (fts_query, chat_id, author_id, author_id, FTS_HIT_COUNT),
        ) as cursor:
            rows = await cursor.fetchall()
    return [row["message_id"] for row in rows]


async def message_window(
    chat_id: int,
    message_id: int,
    *,
    before: int = 10,
    after: int = 14,
) -> SearchEvidence | None:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT
                cs.message_id,
                cs.create_time,
                COALESCE(us.username, 'user:' || cs.user_id) AS author,
                cs.message_text
            FROM chat_stats cs
            LEFT JOIN user_stats us ON us.user_id = cs.user_id
            WHERE cs.chat_id = ?
            AND cs.message_id BETWEEN ? AND ?
            AND cs.message_id IS NOT NULL
            AND cs.message_text IS NOT NULL
            AND cs.message_text <> ''
            AND cs.message_text NOT LIKE '/%'
            ORDER BY cs.message_id;
            """,
            (chat_id, message_id - before, message_id + after),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return None

    messages = [
        ChatMessageText(
            message_id=row["message_id"],
            create_time=row["create_time"],
            author=format_author(row["author"]),
            text=row["message_text"],
        )
        for row in rows
    ]
    return SearchEvidence(
        chat_id=chat_id,
        start_message_id=messages[0].message_id,
        end_message_id=messages[-1].message_id,
        text=build_evidence_text(messages),
        score=0.5,
    )


async def fts_search_windows(
    chat_id: int,
    query: str,
    author_id: int | None,
) -> list[SearchEvidence]:
    message_ids = await fts_hit_message_ids(chat_id, query, author_id)
    windows = []
    for message_id in message_ids:
        window = await message_window(chat_id, message_id)
        if window:
            windows.append(window)
    return windows


def evidence_overlaps(left: SearchEvidence, right: SearchEvidence) -> bool:
    return (
        left.chat_id == right.chat_id
        and left.start_message_id <= right.end_message_id
        and right.start_message_id <= left.end_message_id
    )


def select_evidence(
    vector_windows: list[SearchEvidence],
    fts_windows: list[SearchEvidence],
) -> list[SearchEvidence]:
    selected = []
    for rank in range(max(len(vector_windows), len(fts_windows))):
        for windows in (vector_windows, fts_windows):
            if rank >= len(windows):
                continue
            candidate = windows[rank]
            if any(evidence_overlaps(candidate, item) for item in selected):
                continue
            selected.append(candidate)
            if len(selected) == ANSWER_EVIDENCE_COUNT:
                return selected
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
                "You answer questions about Telegram chat history. "
                "Use only the evidence. Be concise. Cite claims with [1], [2], etc. "
                "If the evidence does not answer the question, say you cannot tell."
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
        "temperature": 0,
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
    return content.strip()


def append_source_links(answer: str, evidence: list[SearchEvidence]) -> str:
    links = []
    for index, item in enumerate(evidence, start=1):
        link = telegram_message_link(item.chat_id, item.citation_message_id)
        if link:
            links.append(f"[{index}]({link})")

    if not links:
        return answer
    return f"{answer}\n\nSources: {' '.join(links)}"


async def semantic_search_answer(
    chat_id: int,
    query: str,
    author_id: int | None,
) -> str | None:
    async with aiohttp.ClientSession() as session:
        query_vector = await embed_search_query(session, query)
        vector_windows = await vector_search_windows(chat_id, query_vector, author_id)
        fts_windows = await fts_search_windows(chat_id, query, author_id)
        evidence = select_evidence(vector_windows, fts_windows)
        if not evidence:
            return None

        answer = await answer_from_evidence(session, query, evidence)
        return append_source_links(answer, evidence)
