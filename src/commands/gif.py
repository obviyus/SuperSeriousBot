import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

GIPHY_API_URL = "https://api.giphy.com/v1/gifs/random"


@usage("/gif")
@example("/gif")
@triggers(["gif"])
@api_key("GIPHY_API_KEY")
@description("Get a random GIF from Giphy.")
async def gif(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random GIF from Giphy"""
    try:
        gif_url = await fetch_random_gif()
        await update.message.reply_animation(animation=gif_url)
    except GiphyAPIError as e:
        await update.message.reply_text(f"Error fetching GIF: {e!s}")


async def fetch_random_gif() -> str:
    """Fetch a random GIF URL from the Giphy API"""
    params = {"api_key": config["API"]["GIPHY_API_KEY"]}

    async with aiohttp.ClientSession() as session:
        async with session.get(GIPHY_API_URL, params=params) as response:
            if response.status != 200:
                raise GiphyAPIError(f"Giphy API returned status code {response.status}")

            data = await response.json()

            if (
                "data" not in data
                or "images" not in data["data"]
                or "original" not in data["data"]["images"]
            ):
                raise GiphyAPIError("Unexpected response structure from Giphy API")

            return data["data"]["images"]["original"]["url"]


class GiphyAPIError(Exception):
    """Exception raised for errors in the Giphy API."""

    pass
