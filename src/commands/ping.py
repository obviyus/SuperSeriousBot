from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage


@triggers(["ping"])
@description("Pong.")
@usage("/ping")
@example("/ping")
async def ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ping with estimated latency.
    """
    await update.message.reply_text(
        f"pong ({(datetime.now().timestamp() - update.message.date.timestamp()) * 1000:.1f}ms)"
    )
