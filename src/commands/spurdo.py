from spurdify import spurdify
from telegram import Update
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage


@usage("/spurdo")
@example("/spurdo")
@triggers(["spurdo"])
@description("Spurdify text.")
async def spurdo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Spurdify text"""
    text = ""
    if not context.args:
        try:
            args: str = update.message.reply_to_message.text or update.message.reply_to_message.caption  # type: ignore
            text = spurdify(args)
        except AttributeError:
            await commands.usage_string(update.message, spurdo)
    else:
        text = spurdify(" ".join(context.args))

    if update.message.reply_to_message:
        await update.message.reply_to_message.reply_text(text=text)
    else:
        await update.message.reply_text(text=text)
