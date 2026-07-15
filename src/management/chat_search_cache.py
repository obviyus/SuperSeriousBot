import asyncio
import importlib
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from config.db import TursoRow, get_db
from config.logger import logger

SEARCH_CACHE_BATCH_SIZE = 1024
SEARCH_CACHE_PATH = "db/chat-search.db"

_sync_lock = asyncio.Lock()


def cache_path() -> Path:
    return Path(os.environ.get("SEARCH_CACHE_PATH", SEARCH_CACHE_PATH))


def open_search_cache():
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    libsql_connect: Any = vars(importlib.import_module("libsql"))["connect"]
    return libsql_connect(
        str(path),
        autocommit=True,
        _check_same_thread=False,
    )


def initialize_search_cache_file() -> None:
    connection = open_search_cache()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_windows (
                remote_id INTEGER NOT NULL UNIQUE,
                chat_id INTEGER NOT NULL,
                start_message_id INTEGER NOT NULL,
                end_message_id INTEGER NOT NULL,
                embedding F32_BLOB(1024) NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_dimension INTEGER NOT NULL,
                UNIQUE (
                    chat_id,
                    start_message_id,
                    end_message_id,
                    embedding_model,
                    embedding_dimension
                )
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS search_windows_chat_idx
            ON search_windows (chat_id, embedding_model, embedding_dimension)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_cache_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                remote_id INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO search_cache_state (singleton, remote_id)
            VALUES (1, 0)
            """
        )
    finally:
        connection.close()


def cached_remote_id() -> int:
    connection = open_search_cache()
    try:
        row = connection.execute(
            "SELECT remote_id FROM search_cache_state WHERE singleton = 1"
        ).fetchone()
        return row[0]
    finally:
        connection.close()


def reset_search_cache() -> None:
    initialize_search_cache_file()
    connection = open_search_cache()
    try:
        connection.execute("BEGIN")
        connection.execute("DELETE FROM search_windows")
        connection.execute(
            "UPDATE search_cache_state SET remote_id = 0 WHERE singleton = 1"
        )
        connection.execute("COMMIT")
    finally:
        connection.close()


def store_search_cache_rows(rows: Sequence[TursoRow]) -> None:
    connection = open_search_cache()
    try:
        connection.execute("BEGIN")
        connection.executemany(
            """
            INSERT INTO search_windows (
                remote_id,
                chat_id,
                start_message_id,
                end_message_id,
                embedding,
                embedding_model,
                embedding_dimension
            )
            VALUES (?, ?, ?, ?, vector32(?), ?, ?)
            ON CONFLICT (
                chat_id,
                start_message_id,
                end_message_id,
                embedding_model,
                embedding_dimension
            )
            DO UPDATE SET
                remote_id = excluded.remote_id,
                embedding = excluded.embedding
            """,
            [
                (
                    row["id"],
                    row["chat_id"],
                    row["start_message_id"],
                    row["end_message_id"],
                    row["embedding"],
                    row["embedding_model"],
                    row["embedding_dimension"],
                )
                for row in rows
            ],
        )
        connection.execute(
            """
            DELETE FROM search_windows AS old
            WHERE EXISTS (
                SELECT 1
                FROM search_windows AS current
                WHERE current.chat_id = old.chat_id
                AND current.start_message_id = old.start_message_id
                AND current.embedding_model = old.embedding_model
                AND current.embedding_dimension = old.embedding_dimension
                AND current.end_message_id > old.end_message_id
            )
            """
        )
        connection.execute(
            """
            UPDATE search_cache_state
            SET remote_id = ?
            WHERE singleton = 1
            """,
            (rows[-1]["id"],),
        )
        connection.execute("COMMIT")
    finally:
        connection.close()


async def fetch_search_cache_rows(after_remote_id: int) -> list[TursoRow]:
    async with get_db() as connection:
        async with connection.execute(
            """
            SELECT
                id,
                chat_id,
                start_message_id,
                end_message_id,
                vector_extract(embedding) AS embedding,
                embedding_model,
                embedding_dimension
            FROM chat_search_windows
            WHERE id > ?
            ORDER BY id
            LIMIT ?
            """,
            (after_remote_id, SEARCH_CACHE_BATCH_SIZE),
        ) as cursor:
            return await cursor.fetchall()


async def sync_search_cache() -> int:
    async with _sync_lock:
        initialize_search_cache_file()
        synced = 0
        while rows := await fetch_search_cache_rows(cached_remote_id()):
            await asyncio.to_thread(store_search_cache_rows, rows)
            synced += len(rows)
        if synced:
            logger.info("Synced %d semantic search windows to local cache", synced)
        return synced
