import httpx
from telegram import Update
from telegram.ext import ContextTypes

import commands
import utils
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

WOLFRAM_SHORT_QUERY = "https://api.wolframalpha.com/v1/result"


@triggers(["calc"])
@description("Perform a WolframAlpha query.")
@usage("/calc")
@example("/calc")
@api_key("WOLFRAM_APP_ID")
async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculate anything using WolframAlpha"""
    if not context.args:
        await commands.usage_string(update.message, calc)
        return

    query: str = " ".join(context.args)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            WOLFRAM_SHORT_QUERY,
            params={"i": query, "appid": config["API"]["WOLFRAM_APP_ID"]},
        )

    if response.status_code != 200:
        await update.message.reply_text("Error: " + response.text)
        return
    else:
        await update.message.reply_text(response.text)
