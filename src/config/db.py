import os

import redis
from telegram.ext import ContextTypes

import aiosqlite

DATABASE_PATH_PREFIX = os.environ.get("DATABASE_PATH_PREFIX", os.getcwd())
PRIMARY_DB_PATH = f"{DATABASE_PATH_PREFIX}/SuperSeriousBot.db"
INDIA_LAW_DB_PATH = f"{DATABASE_PATH_PREFIX}/IndiaLaw.db"


async def get_optimized_connection(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)

    # Apply optimizations
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA busy_timeout = 5000")
    await conn.execute("PRAGMA synchronous = NORMAL")
    await conn.execute("PRAGMA cache_size = 1000000000")
    await conn.execute("PRAGMA foreign_keys = true")
    await conn.execute("PRAGMA temp_store = memory")
    await conn.execute("PRAGMA mmap_size = 268435456")

    # Set row factory
    conn.row_factory = aiosqlite.Row

    return conn


async def get_db():
    return await get_optimized_connection(PRIMARY_DB_PATH)


async def get_law_db():
    return await get_optimized_connection(INDIA_LAW_DB_PATH)


async def execute_transaction(conn: aiosqlite.Connection, queries):
    async with conn.cursor() as cursor:
        await cursor.execute("BEGIN IMMEDIATE")
        try:
            for query, params in queries:
                await cursor.execute(query, params)
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise e


redis = redis.StrictRedis(
    host=f"{os.environ.get('REDIS_HOST', '127.0.0.1')}",
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
    charset="utf-8",
)


async def rebuild_fts5(_: ContextTypes.DEFAULT_TYPE):
    """
    Rebuild the FTS5 table.
    """
    c = sqlite_conn.cursor()
    c.execute("INSERT INTO chat_stats_fts(chat_stats_fts) VALUES('rebuild');")
