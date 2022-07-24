import requests
from telegram import Update
from telegram.ext import ContextTypes

import utils
from config.options import config

WOLFRAM_SHORT_QUERY = "https://api.wolframalpha.com/v1/result"


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculate anything using WolframAlpha"""
    if not context.args:
        await utils.usage_string(update.message)
        return

    query: str = " ".join(context.args)
    response = requests.get(
        WOLFRAM_SHORT_QUERY,
        params={"i": query, "appid": config["API"]["WOLFRAM_APP_ID"]},
    )

    if response.status_code != 200:
        await update.message.reply_text("Error: " + response.text)
        return
    else:
        await update.message.reply_text(response.text)
