import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiosqlite
from redis.asyncio import Redis, from_url
from telegram.ext import ContextTypes

from config import logger

PRIMARY_DB_PATH = Path(os.getenv("DATABASE_PATH_PREFIX", ".")) / "SuperSeriousBot.db"


@asynccontextmanager
async def get_db(write: bool = False) -> AsyncGenerator[aiosqlite.Connection, None]:
    db_path = PRIMARY_DB_PATH
    conn = None
    try:
        conn = await aiosqlite.connect(db_path, isolation_level=None)
        await conn.execute("PRAGMA journal_mode = WAL;")
        await conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = aiosqlite.Row
        yield conn
    finally:
        if conn:
            await conn.close()


REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

MAX_REDIS_RETRIES = 5
REDIS_RETRY_DELAY = 5

redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    global redis_client
    if redis_client is None:
        for attempt in range(MAX_REDIS_RETRIES):
            try:
                redis_client = await from_url(
                    REDIS_URL, encoding="utf-8", decode_responses=True
                )
                await redis_client.ping()
                logger.info("Successfully connected to Redis")
                return redis_client
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis (attempt {attempt + 1}/{MAX_REDIS_RETRIES}): {str(e)}"
                )
                if attempt == MAX_REDIS_RETRIES - 1:
                    logger.error(
                        "Max Redis connection attempts reached. Unable to connect to Redis."
                    )
                    raise
                await asyncio.sleep(REDIS_RETRY_DELAY)
    return redis_client


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")


async def rebuild_fts5(_: ContextTypes.DEFAULT_TYPE):
    """
    Rebuild the FTS5 table.
    """
    async with get_db(write=True) as conn:
        async with conn.cursor() as c:
            await c.execute(
                "INSERT INTO chat_stats_fts(chat_stats_fts) VALUES('rebuild');"
            )
