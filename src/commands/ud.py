import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils


async def ud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search a word on Urban Dictionary.
    """
    word = " ".join(context.args)
    if not word:
        await utils.usage_string(update.message)
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=f"https://api.urbandictionary.com/v0/define?term={word}",
        )
        response = response.json()

    if "error" in response:
        await update.message.reply_text(response["error"])
        return

    if not response["list"]:
        await update.message.reply_text("No results found.")
        return

    result = max(response["list"], key=lambda x: x["thumbs_up"])
    await update.message.reply_text(
        f"<b>{result['word']}</b>\n\n{result['definition']}\n\n<i>{result['example']}</i>\n\n<pre>👍 × {result['thumbs_up']}</pre>",
        parse_mode=ParseMode.HTML,
    )
