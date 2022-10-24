from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage


@usage("/ping")
@example("/ping")
@triggers(["ping"])
@description("Pong.")
async def ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ping with estimated latency.
    """
    time_delta = datetime.now(tz=update.message.date.tzinfo) - update.message.date
    await update.message.reply_text(
        text=f"pong ({time_delta.microseconds / 1000:.2f}ms)",
    )
