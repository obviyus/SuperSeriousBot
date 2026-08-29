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
    description="Answer a calculation or facts query.",
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

    import httpx2

    try:
        async with httpx2.AsyncClient(follow_redirects=True) as session:
            response = await session.get(
                WOLFRAM_SHORT_QUERY,
                params={"i": query, "appid": config.API.WOLFRAM_APP_ID},
                timeout=httpx2.Timeout(10),
            )
            if response.status_code == 200:
                result = response.text
            elif response.status_code == 501:
                result = "❌ I couldn't understand that query."
            elif response.status_code == 403:
                result = "❌ Calculation service is not configured."
            else:
                result = "❌ Calculation service is unavailable."
    except TimeoutError:
        result = "❌ Request timed out"
    except httpx2.HTTPError as e:
        result = f"❌ Connection error: {e!s}"

    await message.reply_text(result)
