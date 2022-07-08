import wolframalpha
from telegram import Update
from telegram.ext import ContextTypes

import utils
from config.options import config

client = wolframalpha.Client(config["WOLFRAM_APP_ID"])


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculate anything using wolframalpha"""
    if not context.args:
        await utils.usage_string(update.message)
        return

    query: str = " ".join(context.args)

    text: str

    result: wolframalpha.Result = client.query(query)

    try:
        text = next(result.results).text
    except StopIteration:
        text = "Invalid query."

    await update.message.reply_text(text=text)
