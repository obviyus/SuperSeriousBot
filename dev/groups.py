import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect("/db/stats.db", check_same_thread=False)
cursor = conn.cursor()


def groups(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Get command usage stats"""
    if not update.message:
        return

    formula: str = "SELECT COUNT(*) FROM sqlite_master AS TABLES WHERE TYPE='table'"
    cursor.execute(formula)
    count = cursor.fetchall()[0]

    update.message.reply_text(text=f"This bot is active in {count[0]} groups.")
