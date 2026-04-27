from telegram import Update
from telegram.ext import ContextTypes

import commands
from config.options import config
from utils.decorators import command
from utils.messages import get_message

WOLFRAM_SHORT_QUERY = "https://api.wolframalpha.com/v1/result"


@command(
    triggers=["calc"],
    usage="/calc [query]",
    example="/calc 300th digit of pi",
    description="Perform a WolframAlpha query.",
    api_key="WOLFRAM_APP_ID",
)
async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not context.args:
        await commands.usage_string(message, calc)
        return

    query = " ".join(context.args).strip()
    if not query or len(query) > 1000:
        await message.reply_text("❌ Invalid query")
        return

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                WOLFRAM_SHORT_QUERY,
                params={"i": query, "appid": config["API"]["WOLFRAM_APP_ID"]},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    result = await response.text()
                elif response.status == 501:
                    result = "❌ WolframAlpha couldn't understand your query"
                elif response.status == 403:
                    result = "❌ API key error"
                else:
                    result = f"❌ Error {response.status}: {await response.text()}"
    except TimeoutError:
        result = "❌ Request timed out"
    except aiohttp.ClientError as e:
        result = f"❌ Connection error: {e!s}"

    await message.reply_text(result)
