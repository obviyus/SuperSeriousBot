import uwuify
from telegram import Update
from telegram.ext import ContextTypes

import utils


async def uwu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Uwuify a message.
    """
    text = (
        update.message.reply_to_message.text
        or update.message.reply_to_message.caption
        or update.message.text
        or update.message.caption
    )

    if not text:
        await utils.usage_string(update.message)
        return

    await update.message.reply_text(uwuify.uwu(text, flags=uwuify.SMILEY | uwuify.YU))
