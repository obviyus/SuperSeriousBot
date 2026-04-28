from telegram import Update
from telegram.ext import ContextTypes

from config.options import config
from utils.decorators import command
from utils.messages import get_message

GIPHY_API_URL = "https://api.giphy.com/v1/gifs/random"


@command(
    triggers=["gif"],
    usage="/gif",
    example="/gif",
    description="Get a random GIF from Giphy.",
    api_key="GIPHY_API_KEY",
)
async def gif(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    import aiohttp

    message = get_message(update)
    if not message:
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(
            GIPHY_API_URL,
            params={"api_key": config.API.GIPHY_API_KEY},
        ) as response:
            if response.status != 200:
                await message.reply_text(
                    f"Error fetching GIF: Giphy API returned status code {response.status}"
                )
                return
            data = await response.json()

    try:
        await message.reply_animation(animation=data["data"]["images"]["original"]["url"])
    except KeyError:
        await message.reply_text(
            "Error fetching GIF: Unexpected response structure from Giphy"
        )
