from telegram import Update
from telegram.ext import ContextTypes

from utils.messages import get_message


async def sed(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)

    if not message:
        return
    """Replace a string in a message."""

    if (
        not message.reply_to_message
        or not message.reply_to_message.text
        or not message.text
    ):
        return

    input_string = message.reply_to_message.text
    parts = message.text.split("/", 2)
    if len(parts) < 3:
        return
    _cmd, search, replace = parts

    await message.reply_to_message.reply_text(input_string.replace(search, replace))
