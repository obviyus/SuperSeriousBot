from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes


async def ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ping with estimated latency.
    """
    await update.message.reply_text(
        f"pong ({(datetime.now().timestamp() - update.message.date.timestamp()) * 1000:.1f}ms)"
    )
