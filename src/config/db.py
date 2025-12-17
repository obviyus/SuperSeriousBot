import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from telegram.ext import ContextTypes

from config import logger

PRIMARY_DB_PATH = Path(os.getenv("DATABASE_PATH_PREFIX", ".")) / "SuperSeriousBot.db"

# AIDEV-NOTE: Singleton connection - SQLite is single-writer, WAL handles concurrent reads.
# This eliminates 60+ connection open/close cycles per message flow.
_db_connection: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()


async def _init_connection() -> aiosqlite.Connection:
    """Initialize the database connection with optimal settings."""
    conn = await aiosqlite.connect(PRIMARY_DB_PATH, isolation_level=None)
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.execute("PRAGMA busy_timeout = 5000;")  # 5s wait on lock contention
    await conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db() -> None:
    """Initialize the database connection pool. Call once at startup."""
    global _db_connection
    async with _db_lock:
        if _db_connection is None:
            _db_connection = await _init_connection()
            logger.info("Database connection initialized")


async def close_db() -> None:
    """Close the database connection. Call once at shutdown."""
    global _db_connection
    async with _db_lock:
        if _db_connection is not None:
            await _db_connection.close()
            _db_connection = None
            logger.info("Database connection closed")


async def _get_connection() -> aiosqlite.Connection:
    """Get the singleton connection, initializing if needed."""
    global _db_connection
    if _db_connection is None:
        async with _db_lock:
            if _db_connection is None:
                _db_connection = await _init_connection()
                logger.info("Database connection initialized (lazy)")
    assert _db_connection is not None
    return _db_connection


@asynccontextmanager
async def get_db(write: bool = False) -> AsyncGenerator[aiosqlite.Connection]:
    """
    Get a database connection. The connection is reused across calls.

    Args:
        write: Hint that this will be a write operation (currently unused,
               kept for API compatibility and future read replica support)
    """
    conn = await _get_connection()
    yield conn


async def optimize_fts5(_: ContextTypes.DEFAULT_TYPE):
    """
    Optimize the FTS5 index by merging segments.

    AIDEV-NOTE: Using 'optimize' instead of 'rebuild'. Rebuild scans the entire
    content table and regenerates the index (minutes on 100M+ rows). Optimize
    merges b-tree segments incrementally - much cheaper, still improves query perf.
    """
    async with get_db(write=True) as conn:
        await conn.execute(
            "INSERT INTO chat_stats_fts(chat_stats_fts) VALUES('optimize');"
        )
        logger.info("FTS5 index optimization completed")
