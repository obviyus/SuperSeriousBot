from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes


async def ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ping command handler.
    """
    await update.message.reply_text(
        f"ping ({(datetime.now().timestamp() - update.message.date.timestamp()) * 1000:.0f}ms)"
    )
