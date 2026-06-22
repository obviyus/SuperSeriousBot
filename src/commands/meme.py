from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["meme"],
    usage="/meme",
    example="/meme",
    description="Get a random meme.",
)
async def meme(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://meme-api.com/gimme") as response:
                if response.status != 200:
                    await message.reply_text("Could not fetch a meme right now.")
                    return
                data = await response.json()
        url = data["url"]
    except (aiohttp.ClientError, KeyError, TypeError):
        await message.reply_text("Could not fetch a meme right now.")
        return

    if url.endswith(".gif"):
        await message.reply_animation(
            animation=url,
        )
    else:
        await message.reply_photo(photo=url)
