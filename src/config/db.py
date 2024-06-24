import os
import sqlite3

import redis
from telegram.ext import ContextTypes

DATABASE_PATH_PREFIX = os.environ.get("DATABASE_PATH_PREFIX", os.getcwd())
PRIMARY_DB_PATH = f"{DATABASE_PATH_PREFIX}/SuperSeriousBot.db"
INDIA_LAW_DB_PATH = f"{DATABASE_PATH_PREFIX}/IndiaLaw.db"

sqlite_conn = sqlite3.connect(
    PRIMARY_DB_PATH,
    check_same_thread=False,
    isolation_level=None,
)

sqlite_conn_law_database = sqlite3.connect(
    INDIA_LAW_DB_PATH,
    check_same_thread=False,
    isolation_level=None,
)

sqlite_conn.row_factory = sqlite3.Row
sqlite_conn_law_database.row_factory = sqlite3.Row

sqlite_conn.execute("PRAGMA journal_mode=WAL;")
sqlite_conn.execute("PRAGMA mmap_size=268435456;")

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
