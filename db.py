import sqlite3

import redis

sqlite_conn = sqlite3.connect("./SuperSeriousBot.db", check_same_thread=False)

redis = redis.StrictRedis(
    host="localhost", port=6379, db=0, decode_responses=True, charset="utf-8"
)

cursor = sqlite_conn.cursor()

# Chat Statistics Table
cursor.execute(
    f"""
    CREATE TABLE IF NOT EXISTS chat_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER
    )
    """
)
