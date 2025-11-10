import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


@usage("/meme")
@example("/meme")
@triggers(["meme"])
@description("Get a random meme.")
async def meme(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Get a random meme"""
    if not message:
        return

    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as response:
            data = await response.json()

    url: str = data["url"]
    if url.endswith(".gif"):
        await message.reply_animation(
            animation=url,
        )
    else:
        await message.reply_photo(photo=url)
