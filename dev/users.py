import sqlite3
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect("/db/stats.db", check_same_thread=False)
cursor = conn.cursor()


def users(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Get total number of users of this bot"""
    if not update.message:
        return

    formula: str = "SELECT name FROM sqlite_master AS TABLES WHERE TYPE='table'"
    cursor.execute(formula)

    total_users = 0
    for table_name in cursor.fetchall():
        logging.info(f"`{table_name[0]}`")
        total_users += cursor.execute(
            f"SELECT COUNT(*) FROM `{table_name[0]}`"
        ).fetchall()[0][0]

    update.message.reply_text(text=f"This bot is used by {total_users} users.")
