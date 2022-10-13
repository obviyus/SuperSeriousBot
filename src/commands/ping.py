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
    time = datetime.now().timestamp() - update.message.date.timestamp()

    await update.message.reply_text(
        "pong ({0:.2f}ms)".format(time).rstrip("0").rstrip(".")
    )
