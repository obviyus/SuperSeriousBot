import argparse
import asyncio
import importlib
import os
from dataclasses import dataclass
from typing import Any

import aiohttp
from dotenv import load_dotenv

from chat_search_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    WINDOW_MESSAGE_COUNT,
    WINDOW_STRIDE,
)
from openrouter_embeddings import openrouter_embeddings, vector32_json


@dataclass(frozen=True)
class SourceMessage:
    message_id: int
    create_time: str
    user_id: int
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", type=int, action="append")
    parser.add_argument("--limit-windows", type=int)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def open_connection():
    load_dotenv(".env")
    libsql_connect: Any = vars(importlib.import_module("libsql"))["connect"]
    return libsql_connect(
        os.environ["TURSO_DATABASE_URL"],
        auth_token=os.environ["TURSO_AUTH_TOKEN"],
        autocommit=True,
        _check_same_thread=False,
    )


def chat_ids(conn, requested_chat_ids: list[int] | None) -> list[int]:
    if requested_chat_ids:
        return requested_chat_ids
    rows = conn.execute(
        """
        SELECT chat_id
        FROM chat_stats
        WHERE message_text IS NOT NULL
        AND message_text <> ''
        GROUP BY chat_id
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()
    return [row[0] for row in rows]


def source_messages(conn, chat_id: int) -> list[SourceMessage]:
    rows = conn.execute(
        """
        SELECT message_id, create_time, user_id, message_text
        FROM chat_stats
        WHERE chat_id = ?
        AND message_id IS NOT NULL
        AND message_text IS NOT NULL
        AND message_text <> ''
        AND message_text NOT LIKE '/%'
        ORDER BY message_id
        """,
        (chat_id,),
    ).fetchall()
    return [
        SourceMessage(
            message_id=row[0],
            create_time=row[1],
            user_id=row[2],
            text=row[3],
        )
        for row in rows
    ]


def existing_windows(conn, chat_id: int) -> set[tuple[int, int]]:
    rows = conn.execute(
        """
        SELECT start_message_id, end_message_id
        FROM chat_search_windows
        WHERE chat_id = ?
        AND embedding_model = ?
        AND embedding_dimension = ?
        """,
        (chat_id, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS),
    ).fetchall()
    return {(row[0], row[1]) for row in rows}


def build_windows(
    chat_id: int,
    messages: list[SourceMessage],
    indexed: set[tuple[int, int]],
) -> list[SearchWindow]:
    windows = []
    for start in range(0, len(messages), WINDOW_STRIDE):
        window_messages = messages[start:start + WINDOW_MESSAGE_COUNT]
        if not window_messages:
            continue
        start_message_id = window_messages[0].message_id
        end_message_id = window_messages[-1].message_id
        if (start_message_id, end_message_id) in indexed:
            continue
        text = "\n".join(
            f"{message.message_id} {message.create_time} user:{message.user_id}: {message.text}"
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


def store_windows(
    conn,
    windows: list[SearchWindow],
    embeddings: list[list[float]],
) -> None:
    conn.executemany(
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


async def backfill() -> None:
    args = parse_args()
    conn = open_connection()
    api_key = os.environ["OPENROUTER_API_KEY"]
    total_inserted = 0

    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids(conn, args.chat_id):
            messages = source_messages(conn, chat_id)
            indexed = existing_windows(conn, chat_id)
            windows = build_windows(chat_id, messages, indexed)
            if args.limit_windows is not None:
                remaining = args.limit_windows - total_inserted
                if remaining <= 0:
                    break
                windows = windows[:remaining]

            print(
                f"chat_id={chat_id} messages={len(messages):,} missing_windows={len(windows):,}"
            )

            for offset in range(0, len(windows), args.batch_size):
                batch = windows[offset:offset + args.batch_size]
                embeddings = await openrouter_embeddings(
                    session,
                    api_key,
                    EMBEDDING_MODEL,
                    [window.text for window in batch],
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                store_windows(conn, batch, embeddings)
                total_inserted += len(batch)
                print(f"indexed_windows={total_inserted:,}")

    conn.close()


if __name__ == "__main__":
    asyncio.run(backfill())
