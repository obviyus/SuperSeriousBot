from dataclasses import dataclass
from datetime import datetime

from chat_search_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    UTTERANCE_EMBEDDING_DIMENSIONS,
    UTTERANCE_GAP_SECONDS,
    UTTERANCE_MAX_MESSAGES,
    WINDOW_MESSAGE_COUNT,
    WINDOW_STRIDE,
)
from config.db import get_db
from management.chat_search_cache import reset_search_cache, sync_search_cache
from openrouter_embeddings import openrouter_embeddings, vector32_json

INDEX_BATCH_WINDOWS = 64
MIN_MESSAGE_ID = -(1 << 63)


@dataclass(frozen=True)
class SourceMessage:
    message_id: int
    create_time: str
    author: str
    text: str
    user_id: int = 0


@dataclass(frozen=True)
class SearchWindow:
    chat_id: int
    start_message_id: int
    end_message_id: int
    start_time: str
    end_time: str
    message_count: int
    text: str


@dataclass(frozen=True)
class SearchUtterance:
    chat_id: int
    start_message_id: int
    end_message_id: int
    user_id: int
    author: str
    start_time: str
    end_time: str
    message_count: int
    text: str


def format_author(author: object) -> str:
    author_text = str(author)
    return author_text if author_text.startswith("user:") else f"@{author_text}"


def build_windows(
    chat_id: int,
    messages: list[SourceMessage],
    indexed: set[tuple[int, int]],
) -> list[SearchWindow]:
    windows = []
    for start in range(0, len(messages), WINDOW_STRIDE):
        window_messages = messages[start : start + WINDOW_MESSAGE_COUNT]
        start_message_id = window_messages[0].message_id
        end_message_id = window_messages[-1].message_id
        if (start_message_id, end_message_id) in indexed:
            continue
        text = "\n".join(
            f"{message.message_id} {message.create_time} {message.author}: {message.text}"
            for message in window_messages
        )
        windows.append(
            SearchWindow(
                chat_id=chat_id,
                start_message_id=start_message_id,
                end_message_id=end_message_id,
                start_time=window_messages[0].create_time,
                end_time=window_messages[-1].create_time,
                message_count=len(window_messages),
                text=text,
            )
        )
    return windows


def build_utterances(
    chat_id: int,
    messages: list[SourceMessage],
    indexed: set[tuple[int, int]],
) -> list[SearchUtterance]:
    groups: list[list[SourceMessage]] = []
    current: list[SourceMessage] = []
    for message in messages:
        if current:
            gap = datetime.fromisoformat(message.create_time) - datetime.fromisoformat(
                current[-1].create_time
            )
            if (
                message.user_id != current[-1].user_id
                or gap.total_seconds() > UTTERANCE_GAP_SECONDS
                or len(current) == UTTERANCE_MAX_MESSAGES
            ):
                groups.append(current)
                current = []
        current.append(message)
    if current:
        groups.append(current)

    utterances = []
    for group in groups:
        first = group[0]
        last = group[-1]
        if (first.message_id, last.message_id) in indexed:
            continue
        utterances.append(
            SearchUtterance(
                chat_id=chat_id,
                start_message_id=first.message_id,
                end_message_id=last.message_id,
                user_id=first.user_id,
                author=first.author,
                start_time=first.create_time,
                end_time=last.create_time,
                message_count=len(group),
                text="\n".join(
                    f"{message.message_id} {message.text}" for message in group
                ),
            )
        )
    return utterances


async def searchable_chat_ids() -> list[int]:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT chat_id
            FROM group_settings
            WHERE fts = 1
            ORDER BY chat_id
            """
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [row["chat_id"] for row in rows]


async def source_chat_ids() -> list[int]:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT chat_id
            FROM chat_stats
            WHERE message_text IS NOT NULL
            AND message_text <> ''
            GROUP BY chat_id
            ORDER BY COUNT(*) DESC
            """
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [row["chat_id"] for row in rows]


async def resume_window_start(chat_id: int) -> int:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT start_message_id, message_count
            FROM chat_search_windows
            WHERE chat_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            ORDER BY start_message_id DESC
            LIMIT ?
            """,
            (
                chat_id,
                EMBEDDING_MODEL,
                EMBEDDING_DIMENSIONS,
                (WINDOW_MESSAGE_COUNT + WINDOW_STRIDE - 1) // WINDOW_STRIDE,
            ),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    partial_starts = [
        row["start_message_id"]
        for row in rows
        if row["message_count"] < WINDOW_MESSAGE_COUNT
    ]
    if partial_starts:
        return min(partial_starts)
    return rows[0]["start_message_id"] if rows else MIN_MESSAGE_ID


async def source_messages(
    chat_id: int,
    start_message_id: int,
    window_limit: int,
) -> list[SourceMessage]:
    row_limit = max(
        WINDOW_STRIDE * window_limit + WINDOW_MESSAGE_COUNT,
        UTTERANCE_MAX_MESSAGES * window_limit + 1,
    )
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT
                cs.message_id,
                cs.user_id,
                cs.create_time,
                COALESCE(us.username, 'user:' || cs.user_id) AS author,
                cs.message_text
            FROM chat_stats cs
            LEFT JOIN user_stats us ON us.user_id = cs.user_id
            WHERE cs.chat_id = ?
            AND cs.message_id >= ?
            AND cs.message_id IS NOT NULL
            AND cs.message_text IS NOT NULL
            AND cs.message_text <> ''
            AND cs.message_text NOT LIKE '/%'
            ORDER BY cs.message_id
            LIMIT ?
            """,
            (chat_id, start_message_id, row_limit),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [
        SourceMessage(
            message_id=row["message_id"],
            create_time=row["create_time"],
            author=format_author(row["author"]),
            text=row["message_text"],
            user_id=row["user_id"],
        )
        for row in rows
    ]


async def existing_windows(
    chat_id: int,
    start_message_id: int,
) -> set[tuple[int, int]]:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT start_message_id, end_message_id
            FROM chat_search_windows
            WHERE chat_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            AND start_message_id >= ?
            """,
            (
                chat_id,
                EMBEDDING_MODEL,
                EMBEDDING_DIMENSIONS,
                start_message_id,
            ),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return {(row["start_message_id"], row["end_message_id"]) for row in rows}


async def resume_utterance_start(chat_id: int) -> int:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT MAX(start_message_id) AS start_message_id
            FROM chat_search_utterances
            WHERE chat_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            """,
            (chat_id, EMBEDDING_MODEL, UTTERANCE_EMBEDDING_DIMENSIONS),
        ) as cursor,
    ):
        row = await cursor.fetchone()
    return (
        row["start_message_id"]
        if row and row["start_message_id"] is not None
        else MIN_MESSAGE_ID
    )


async def existing_utterances(
    chat_id: int,
    start_message_id: int,
) -> set[tuple[int, int]]:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT start_message_id, end_message_id
            FROM chat_search_utterances
            WHERE chat_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            AND start_message_id >= ?
            """,
            (
                chat_id,
                EMBEDDING_MODEL,
                UTTERANCE_EMBEDDING_DIMENSIONS,
                start_message_id,
            ),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return {(row["start_message_id"], row["end_message_id"]) for row in rows}


async def store_windows(
    windows: list[SearchWindow],
    embeddings: list[list[float]],
) -> None:
    async with get_db() as conn:
        await conn.executemany(
            """
            INSERT INTO chat_search_windows (
                chat_id,
                start_message_id,
                end_message_id,
                start_time,
                end_time,
                message_count,
                message_text,
                embedding,
                embedding_model,
                embedding_dimension,
                update_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (
                chat_id,
                start_message_id,
                end_message_id,
                embedding_model,
                embedding_dimension
            )
            DO UPDATE SET
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                message_count = excluded.message_count,
                message_text = excluded.message_text,
                embedding = excluded.embedding,
                update_time = CURRENT_TIMESTAMP
            """,
            [
                (
                    window.chat_id,
                    window.start_message_id,
                    window.end_message_id,
                    window.start_time,
                    window.end_time,
                    window.message_count,
                    window.text,
                    vector32_json(embedding),
                    EMBEDDING_MODEL,
                    EMBEDDING_DIMENSIONS,
                )
                for window, embedding in zip(windows, embeddings, strict=True)
            ],
        )
        await conn.executemany(
            """
            DELETE FROM chat_search_windows
            WHERE chat_id = ?
            AND start_message_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            AND end_message_id < ?
            """,
            [
                (
                    window.chat_id,
                    window.start_message_id,
                    EMBEDDING_MODEL,
                    EMBEDDING_DIMENSIONS,
                    window.end_message_id,
                )
                for window in windows
            ],
        )


async def store_utterances(
    utterances: list[SearchUtterance],
    embeddings: list[list[float]],
) -> None:
    async with get_db() as conn:
        await conn.executemany(
            """
            INSERT OR REPLACE INTO chat_search_utterances (
                chat_id,
                start_message_id,
                end_message_id,
                user_id,
                author,
                start_time,
                end_time,
                message_count,
                message_text,
                embedding,
                embedding_model,
                embedding_dimension,
                update_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, vector32(?), ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                (
                    utterance.chat_id,
                    utterance.start_message_id,
                    utterance.end_message_id,
                    utterance.user_id,
                    utterance.author,
                    utterance.start_time,
                    utterance.end_time,
                    utterance.message_count,
                    utterance.text,
                    vector32_json(embedding),
                    EMBEDDING_MODEL,
                    UTTERANCE_EMBEDDING_DIMENSIONS,
                )
                for utterance, embedding in zip(utterances, embeddings, strict=True)
            ],
        )


async def index_window_batch(
    chat_id: int,
    start_message_id: int,
    window_limit: int,
    *,
    skip_indexed: bool,
) -> tuple[int, int | None]:
    messages = await source_messages(chat_id, start_message_id, window_limit)
    if not messages:
        return 0, None
    indexed = (
        await existing_windows(chat_id, start_message_id) if skip_indexed else set()
    )
    windows = build_windows(chat_id, messages, indexed)[:window_limit]
    if not windows:
        return 0, None
    embeddings = await openrouter_embeddings(
        EMBEDDING_MODEL,
        [window.text for window in windows],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    await store_windows(windows, embeddings)
    last_start_index = next(
        index
        for index, message in enumerate(messages)
        if message.message_id == windows[-1].start_message_id
    )
    next_start_index = last_start_index + WINDOW_STRIDE
    next_start_message_id = (
        messages[next_start_index].message_id
        if next_start_index < len(messages)
        else None
    )
    return len(windows), next_start_message_id


async def index_chat_windows(
    chat_id: int,
    window_limit: int,
) -> int:
    indexed, _ = await index_window_batch(
        chat_id,
        await resume_window_start(chat_id),
        window_limit,
        skip_indexed=True,
    )
    return indexed


async def index_utterance_batch(
    chat_id: int,
    start_message_id: int,
    utterance_limit: int,
    *,
    skip_indexed: bool,
) -> tuple[int, int | None]:
    messages = await source_messages(chat_id, start_message_id, utterance_limit)
    if not messages:
        return 0, None
    indexed = (
        await existing_utterances(chat_id, start_message_id) if skip_indexed else set()
    )
    utterances = build_utterances(chat_id, messages, indexed)[:utterance_limit]
    if not utterances:
        return 0, None
    embeddings = await openrouter_embeddings(
        EMBEDDING_MODEL,
        [f"{utterance.author}: {utterance.text}" for utterance in utterances],
        dimensions=UTTERANCE_EMBEDDING_DIMENSIONS,
    )
    await store_utterances(utterances, embeddings)
    last_end_index = next(
        index
        for index, message in enumerate(messages)
        if message.message_id == utterances[-1].end_message_id
    )
    next_start_index = last_end_index + 1
    next_start_message_id = (
        messages[next_start_index].message_id
        if next_start_index < len(messages)
        else None
    )
    return len(utterances), next_start_message_id


async def index_chat_utterances(
    chat_id: int,
    utterance_limit: int,
) -> int:
    indexed, _ = await index_utterance_batch(
        chat_id,
        await resume_utterance_start(chat_id),
        utterance_limit,
        skip_indexed=True,
    )
    return indexed


async def index_pending_utterances(
    *,
    chat_ids: list[int],
    utterance_limit: int = INDEX_BATCH_WINDOWS,
) -> int:
    if not chat_ids:
        return 0

    indexed = 0
    backlogged = []
    per_chat_limit = max(1, utterance_limit // len(chat_ids))
    for chat_id in chat_ids:
        remaining = utterance_limit - indexed
        if remaining <= 0:
            break
        chat_limit = min(per_chat_limit, remaining)
        chat_indexed = await index_chat_utterances(chat_id, chat_limit)
        indexed += chat_indexed
        if chat_indexed == chat_limit:
            backlogged.append(chat_id)

    for chat_id in backlogged:
        remaining = utterance_limit - indexed
        if remaining <= 0:
            break
        indexed += await index_chat_utterances(chat_id, remaining)
    await sync_search_cache()
    return indexed


async def index_pending_windows(
    *,
    chat_ids: list[int],
    window_limit: int = INDEX_BATCH_WINDOWS,
) -> int:
    if not chat_ids:
        return 0

    indexed = 0
    backlogged = []
    per_chat_limit = max(1, window_limit // len(chat_ids))
    for chat_id in chat_ids:
        remaining = window_limit - indexed
        if remaining <= 0:
            break
        chat_limit = min(per_chat_limit, remaining)
        chat_indexed = await index_chat_windows(chat_id, chat_limit)
        indexed += chat_indexed
        if chat_indexed == chat_limit:
            backlogged.append(chat_id)

    for chat_id in backlogged:
        remaining = window_limit - indexed
        if remaining <= 0:
            break
        indexed += await index_chat_windows(chat_id, remaining)
    await sync_search_cache()
    return indexed


async def refresh_windows(chat_ids: list[int]) -> int:
    refreshed = 0
    for chat_id in chat_ids:
        start_message_id = MIN_MESSAGE_ID
        while True:
            batch_size, next_start_message_id = await index_window_batch(
                chat_id,
                start_message_id,
                INDEX_BATCH_WINDOWS,
                skip_indexed=False,
            )
            refreshed += batch_size
            if batch_size < INDEX_BATCH_WINDOWS or next_start_message_id is None:
                break
            start_message_id = next_start_message_id
    reset_search_cache()
    await sync_search_cache()
    return refreshed


async def refresh_utterances(chat_ids: list[int]) -> int:
    refreshed = 0
    for chat_id in chat_ids:
        start_message_id = MIN_MESSAGE_ID
        while True:
            batch_size, next_start_message_id = await index_utterance_batch(
                chat_id,
                start_message_id,
                INDEX_BATCH_WINDOWS,
                skip_indexed=False,
            )
            refreshed += batch_size
            if batch_size < INDEX_BATCH_WINDOWS or next_start_message_id is None:
                break
            start_message_id = next_start_message_id
    await sync_search_cache()
    return refreshed
