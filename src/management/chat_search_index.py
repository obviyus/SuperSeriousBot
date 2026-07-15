from dataclasses import dataclass

import aiohttp

from chat_search_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    WINDOW_MESSAGE_COUNT,
    WINDOW_STRIDE,
)
from config.db import get_db
from management.chat_search_cache import reset_search_cache, sync_search_cache
from openrouter_embeddings import openrouter_embeddings, vector32_json

INDEX_BATCH_WINDOWS = 64


@dataclass(frozen=True)
class SourceMessage:
    message_id: int
    create_time: str
    author: str
    text: str


@dataclass(frozen=True)
class SearchWindow:
    chat_id: int
    start_message_id: int
    end_message_id: int
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


async def searchable_chat_ids() -> list[int]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT settings.chat_id
            FROM group_settings settings
            LEFT JOIN chat_search_windows windows
                ON windows.chat_id = settings.chat_id
            WHERE settings.fts = 1
            AND EXISTS (
                SELECT 1
                FROM chat_stats messages
                WHERE messages.chat_id = settings.chat_id
                AND messages.message_text IS NOT NULL
                AND messages.message_text <> ''
            )
            GROUP BY settings.chat_id
            ORDER BY MAX(windows.update_time), settings.chat_id
            """
        ) as cursor:
            rows = await cursor.fetchall()
    return [row["chat_id"] for row in rows]


async def source_chat_ids() -> list[int]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT chat_id
            FROM chat_stats
            WHERE message_text IS NOT NULL
            AND message_text <> ''
            GROUP BY chat_id
            ORDER BY COUNT(*) DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
    return [row["chat_id"] for row in rows]


async def resume_window_start(chat_id: int) -> int | None:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT COALESCE(
                MIN(
                    CASE
                        WHEN message_count < ? THEN start_message_id
                    END
                ),
                MAX(start_message_id)
            ) AS start_message_id
            FROM chat_search_windows
            WHERE chat_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            """,
            (
                WINDOW_MESSAGE_COUNT,
                chat_id,
                EMBEDDING_MODEL,
                EMBEDDING_DIMENSIONS,
            ),
        ) as cursor:
            row = await cursor.fetchone()
    return row["start_message_id"] if row and row["start_message_id"] else None


async def source_messages(
    chat_id: int,
    start_message_id: int | None,
    window_limit: int,
) -> list[SourceMessage]:
    row_limit = WINDOW_STRIDE * window_limit + WINDOW_MESSAGE_COUNT
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
            AND (? IS NULL OR cs.message_id >= ?)
            AND cs.message_id IS NOT NULL
            AND cs.message_text IS NOT NULL
            AND cs.message_text <> ''
            AND cs.message_text NOT LIKE '/%'
            ORDER BY cs.message_id
            LIMIT ?
            """,
            (chat_id, start_message_id, start_message_id, row_limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        SourceMessage(
            message_id=row["message_id"],
            create_time=row["create_time"],
            author=format_author(row["author"]),
            text=row["message_text"],
        )
        for row in rows
    ]


async def existing_windows(
    chat_id: int,
    start_message_id: int | None,
) -> set[tuple[int, int]]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT start_message_id, end_message_id
            FROM chat_search_windows
            WHERE chat_id = ?
            AND embedding_model = ?
            AND embedding_dimension = ?
            AND (? IS NULL OR start_message_id >= ?)
            """,
            (
                chat_id,
                EMBEDDING_MODEL,
                EMBEDDING_DIMENSIONS,
                start_message_id,
                start_message_id,
            ),
        ) as cursor:
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
        await conn.execute(
            """
            DELETE FROM chat_search_windows AS old
            WHERE old.chat_id = ?
            AND old.embedding_model = ?
            AND old.embedding_dimension = ?
            AND EXISTS (
                SELECT 1
                FROM chat_search_windows AS current
                WHERE current.chat_id = old.chat_id
                AND current.start_message_id = old.start_message_id
                AND current.embedding_model = old.embedding_model
                AND current.embedding_dimension = old.embedding_dimension
                AND current.end_message_id > old.end_message_id
            )
            """,
            (windows[0].chat_id, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS),
        )


async def index_window_batch(
    session: aiohttp.ClientSession,
    api_key: str,
    chat_id: int,
    start_message_id: int | None,
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
        session,
        api_key,
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
    session: aiohttp.ClientSession,
    api_key: str,
    chat_id: int,
    window_limit: int,
) -> int:
    indexed, _ = await index_window_batch(
        session,
        api_key,
        chat_id,
        await resume_window_start(chat_id),
        window_limit,
        skip_indexed=True,
    )
    return indexed


async def index_pending_windows(
    api_key: str,
    *,
    chat_ids: list[int],
    window_limit: int = INDEX_BATCH_WINDOWS,
) -> int:
    if not chat_ids:
        return 0

    indexed = 0
    backlogged = []
    per_chat_limit = max(1, window_limit // len(chat_ids))
    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            remaining = window_limit - indexed
            if remaining <= 0:
                break
            chat_limit = min(per_chat_limit, remaining)
            chat_indexed = await index_chat_windows(
                session,
                api_key,
                chat_id,
                chat_limit,
            )
            indexed += chat_indexed
            if chat_indexed == chat_limit:
                backlogged.append(chat_id)

        for chat_id in backlogged:
            remaining = window_limit - indexed
            if remaining <= 0:
                break
            indexed += await index_chat_windows(
                session,
                api_key,
                chat_id,
                remaining,
            )
    await sync_search_cache()
    return indexed


async def refresh_windows(api_key: str, chat_ids: list[int]) -> int:
    refreshed = 0
    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            start_message_id = None
            while True:
                batch_size, next_start_message_id = await index_window_batch(
                    session,
                    api_key,
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
