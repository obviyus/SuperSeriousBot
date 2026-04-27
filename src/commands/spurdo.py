from spurdify import spurdify
from telegram import Update
from telegram.ext import ContextTypes

import commands
from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["spurdo"],
    usage="/spurdo",
    example="/spurdo",
    description="Spurdify text.",
)
async def spurdo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    text = ""
    if not context.args:
        if message.reply_to_message:
            args: str | None = (
                message.reply_to_message.text or message.reply_to_message.caption
            )
            if args:
                text = spurdify(args)
            else:
                await commands.usage_string(message, spurdo)
                return
        else:
            await commands.usage_string(message, spurdo)
            return
    else:
        text = spurdify(" ".join(context.args))

    if message.reply_to_message:
        await message.reply_to_message.reply_text(text=text)
    else:
        await message.reply_text(text=text)
