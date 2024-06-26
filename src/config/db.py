import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import aiosqlite
from redis.asyncio import Redis, from_url
from telegram.ext import ContextTypes

from config import logger

DATABASE_PATH_PREFIX = os.environ.get("DATABASE_PATH_PREFIX", os.getcwd())
PRIMARY_DB_PATH = f"{DATABASE_PATH_PREFIX}/SuperSeriousBot.db"
MAX_CONNECTIONS = 10
ACQUIRE_TIMEOUT = 5  # seconds


class DatabasePool:
    def __init__(self, db_path: str, max_connections: int):
        self.db_path = db_path
        self.max_connections = max_connections
        self.read_pool = asyncio.Queue(max_connections - 1)
        self.write_connection = None
        self.write_lock = asyncio.Lock()
        self.initialized = False

    async def initialize(self):
        logger.info("Initializing database pool...")
        for _ in range(self.max_connections - 1):
            conn = await self._create_connection(readonly=True)
            await self.read_pool.put(conn)
        self.write_connection = await self._create_connection(readonly=False)
        self.initialized = True
        logger.info("Database pool initialized successfully.")

    async def _create_connection(self, readonly: bool) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.db_path, uri=True)
        logger.info(f"Created {'readonly' if readonly else 'write'} connection")

        # Apply optimizations
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA busy_timeout = 5000")
        await conn.execute("PRAGMA synchronous = NORMAL")
        await conn.execute("PRAGMA cache_size = 1000000000")
        await conn.execute("PRAGMA foreign_keys = true")
        await conn.execute("PRAGMA temp_store = memory")
        await conn.execute("PRAGMA mmap_size = 268435456")

        if readonly:
            await conn.execute("PRAGMA query_only = ON")

        conn.row_factory = aiosqlite.Row
        return conn

    async def acquire(self, write: bool = False) -> aiosqlite.Connection:
        if not self.initialized:
            raise RuntimeError(
                "Database pool is not initialized. Call initialize() first."
            )

        if write:
            async with self.write_lock:
                return self.write_connection
        else:
            try:
                return await asyncio.wait_for(
                    self.read_pool.get(), timeout=ACQUIRE_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout while acquiring read connection. Creating a new one."
                )
                return await self._create_connection(readonly=True)

    async def release(self, conn: aiosqlite.Connection, write: bool = False):
        if not write:
            await self.read_pool.put(conn)

    async def close(self):
        logger.info("Closing database pool...")
        while not self.read_pool.empty():
            conn = await self.read_pool.get()
            await conn.close()
        if self.write_connection:
            await self.write_connection.close()
        self.initialized = False
        logger.info("Database pool closed.")


db_pool = DatabasePool(PRIMARY_DB_PATH, MAX_CONNECTIONS)


async def initialize_db_pool():
    await db_pool.initialize()


@asynccontextmanager
async def get_db(write: bool = False) -> AsyncGenerator[aiosqlite.Connection, None]:
    if not db_pool.initialized:
        logger.warning("Database pool not initialized. Attempting to initialize now...")
        await initialize_db_pool()

    conn = await db_pool.acquire(write)
    try:
        yield conn
    finally:
        await db_pool.release(conn, write)


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
