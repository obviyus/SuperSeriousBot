import uwuify
from telegram import Update
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage


@triggers(["uwu"])
@usage("/uwu [text]")
@example("/uwu Hello")
@description("Uwuify a message. Reply to a message to uwuify it.")
async def uwu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Uwuify a message.
    """
    if update.message.reply_to_message:
        text = (
            update.message.reply_to_message.text
            or update.message.reply_to_message.caption
        )
    else:
        text = " ".join(context.args)

    if not text:
        await commands.usage_string(update.message, uwu)
        return

    await update.message.reply_text(uwuify.uwu(text, flags=uwuify.SMILEY | uwuify.YU))
