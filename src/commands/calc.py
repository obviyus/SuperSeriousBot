import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

import commands
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

WOLFRAM_SHORT_QUERY = "https://api.wolframalpha.com/v1/result"


@triggers(["calc"])
@usage("/calc [query]")
@api_key("WOLFRAM_APP_ID")
@example("/calc 300th digit of pi")
@description("Perform a WolframAlpha query.")
async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculate anything using WolframAlpha"""
    if not context.args:
        await commands.usage_string(update.message, calc)
        return

    query: str = " ".join(context.args)
    result = await fetch_wolfram_result(query)
    await update.message.reply_text(result)


async def fetch_wolfram_result(query: str) -> str:
    """Fetch result from WolframAlpha API"""
    params = {"i": query, "appid": config["API"]["WOLFRAM_APP_ID"]}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(WOLFRAM_SHORT_QUERY, params=params) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    return f"Error: HTTP {response.status}. {await response.text()}"
        except aiohttp.ClientError as e:
            return f"Error: Unable to connect to WolframAlpha API. {str(e)}"
