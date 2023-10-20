import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage


@triggers(["ud"])
@usage("/ud [word]")
@example("/ud racism")
@description("Search a word on Urban Dictionary.")
async def ud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search a word on Urban Dictionary.
    """
    word = " ".join(context.args)
    if not word:
        await commands.usage_string(update.message, ud)
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=f"https://api.urbandictionary.com/v0/define?term={word}",
            headers={
                "User-Agent": "SuperSeriousBot",
                "Accept": "application/json",
            },
        )
        response = response.json()

    if "error" in response:
        await update.message.reply_text(response["error"])
        return

    if not response["list"]:
        await update.message.reply_text("No results found.")
        return

    result = max(response["list"], key=lambda x: x["thumbs_up"])

    definition = (
        result["definition"]
        if len(result["definition"]) <= 1000
        else result["definition"][:1000] + "..."
    ).strip()

    ud_example = (
        result["example"]
        if len(result["example"]) <= 1000
        else result["example"][:1000] + "..."
    ).strip()

    await update.message.reply_text(
        f"<a href='{result['permalink']}'><b>{result['word']}</b></a>"
        f"\n\n{definition}"
        f"\n\n<i>{ud_example}</i>"
        f"\n\n<pre>👍 × {result['thumbs_up']}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
