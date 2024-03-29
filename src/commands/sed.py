from telegram import Update
from telegram.ext import ContextTypes


async def sed(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Replace a string in a message."""

    input_string = update.message.reply_to_message.text
    _, search, replace = update.message.text.split("/", 2)

    await update.message.reply_to_message.reply_text(
        input_string.replace(search, replace)
    )
