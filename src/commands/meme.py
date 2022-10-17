import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage


@usage("/meme")
@example("/meme")
@triggers(["meme"])
@description("Get a random meme.")
async def meme(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random meme"""
    if not update.message:
        return

    async with httpx.AsyncClient() as client:
        response = await client.get("https://meme-api.herokuapp.com/gimme")

    url: str = response.json()["url"]
    if url.endswith(".gif"):
        await update.message.reply_animation(
            animation=url,
        )
    else:
        await update.message.reply_photo(photo=url)


@usage("/tyag")
@example("/tyag")
@triggers(["tyag"])
@description("Get Elden Ring playtime for @MyTransformerIsFine.")
async def tyag(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get Elden Ring playtime for @MyTransformerIsFine."""
    with httpx.Client() as client:
        response = client.get("https://decapi.me/steam/hours/76561198090799457/1245620")
        response_readable = client.get(
            "https://decapi.me/steam/hours/76561198090799457/1245620/readable"
        )

        await update.message.reply_text(
            text=f"@MyTransformerIsFine has played Elden Ring for <b>{response.text}</b> ({response_readable.text.strip()}).",
            parse_mode=ParseMode.HTML,
        )
