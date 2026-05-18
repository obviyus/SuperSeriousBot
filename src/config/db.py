import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from telegram.ext import ContextTypes

from config import logger

PRIMARY_DB_PATH = Path(os.getenv("DATABASE_PATH_PREFIX", ".")) / "SuperSeriousBot.db"

_init_lock = asyncio.Lock()


async def _open_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(PRIMARY_DB_PATH, isolation_level=None)
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.execute("PRAGMA busy_timeout = 5000;")  # 5s wait on lock contention
    await conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db() -> None:
    async with _init_lock:
        conn = await _open_connection()
        try:
            await conn.execute("PRAGMA journal_mode = WAL;")
        finally:
            await conn.close()
        logger.info("Database connection initialized")


async def close_db() -> None:
    logger.info("Database connection closed")


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection]:
    conn = await _open_connection()
    try:
        yield conn
    finally:
        await conn.close()


async def optimize_fts5(_: ContextTypes.DEFAULT_TYPE):
    """
    Optimize the FTS5 index by merging segments.

    AIDEV-NOTE: Using 'optimize' instead of 'rebuild'. Rebuild scans the entire
    content table and regenerates the index (minutes on 100M+ rows). Optimize
    merges b-tree segments incrementally - much cheaper, still improves query perf.
    """
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO chat_stats_fts(chat_stats_fts) VALUES('optimize');"
        )
        logger.info("FTS5 index optimization completed")
