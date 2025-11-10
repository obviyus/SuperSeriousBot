import uwuify
from telegram import Update
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


@triggers(["uwu"])
@usage("/uwu [text]")
@example("/uwu Hello")
@description("Uwuify a message. Reply to a message to uwuify it.")
async def uwu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """
    Uwuify a message.
    """
    text: str | None = None
    if message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption
    elif context.args:
        text = " ".join(context.args)

    if not text:
        await commands.usage_string(message, uwu)
        return

    await message.reply_text(uwuify.uwu(text, flags=uwuify.SMILEY | uwuify.YU))
