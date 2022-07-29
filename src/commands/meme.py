import httpx
from telegram import Update
from telegram.ext import ContextTypes


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
