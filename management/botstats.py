from telegram import Update
from telegram.ext import ContextTypes

from db import sqlite_conn


async def get_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get number of users of this bot.
    """

    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_stats;")

    await update.message.reply_text(
        f"@{context.bot.username} is used by <b>{cursor.fetchone()[0]}</b> users."
    )


async def get_total_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get number of chats this bot is used in.
    """

    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_stats;")

    await update.message.reply_text(
        f"@{context.bot.username} is used in <b>{cursor.fetchone()[0]}</b> groups."
    )
