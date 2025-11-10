from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


@usage("/ping")
@example("/ping")
@triggers(["ping"])
@description("Pong.")
async def ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """
    Ping with estimated latency.
    """
    time_delta = datetime.now(tz=message.date.tzinfo) - message.date
    await message.reply_text(
        text=f"pong ({time_delta.microseconds / 1000:.2f}ms)",
    )
