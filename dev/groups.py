import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect('/db/stats.db', check_same_thread=False)
cursor = conn.cursor()


def groups(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get command usage stats"""
    if not update.message:
        return

    text: str
    formula: str = "SELECT COUNT(*) FROM sqlite_master AS TABLES WHERE TYPE='table'"

    if update.effective_chat.type != 'private':
        cursor.execute(formula)
        count = cursor.fetchall()[0]

        text = f"This bot is active in {count[0]} groups."
    else:
        text = "This command does not work in private chats."

    update.message.reply_text(text=text)
