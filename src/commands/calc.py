from functools import lru_cache

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

import commands
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

WOLFRAM_SHORT_QUERY = "https://api.wolframalpha.com/v1/result"


@lru_cache(maxsize=100)
async def fetch_wolfram_result(query: str) -> str:
    """Fetch result from WolframAlpha API with caching"""
    params = {"i": query, "appid": config["API"]["WOLFRAM_APP_ID"]}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                WOLFRAM_SHORT_QUERY, params=params, timeout=10
            ) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 501:
                    return "❌ WolframAlpha couldn't understand your query"
                elif response.status == 403:
                    return "❌ API key error"
                else:
                    return f"❌ Error {response.status}: {await response.text()}"
        except aiohttp.ClientTimeout:
            return "❌ Request timed out"
        except aiohttp.ClientError as e:
            return f"❌ Connection error: {e!s}"


def sanitize_query(query: str) -> str | None:
    """Validate and sanitize the input query"""
    query = query.strip()
    if not query or len(query) > 1000:
        return None
    return query


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

    query = sanitize_query(" ".join(context.args))
    if not query:
        await update.message.reply_text("❌ Invalid query")
        return

    result = await fetch_wolfram_result(query)
    await update.message.reply_text(result)
