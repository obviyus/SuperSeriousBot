from typing import Dict

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from config.options import config
from utils.decorators import api_key, description, example, triggers, usage


@usage("/gif")
@example("/gif")
@triggers(["gif"])
@api_key("GIPHY_API_KEY")
@description("Get a random GIF from giphy.")
async def gif(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random GIF from giphy"""
    params: Dict[str, str] = {"api_key": config["API"]["GIPHY_API_KEY"]}

    # TODO: Choose a better API, Giphy's results repeat a lot
    url: str = "https://api.giphy.com/v1/gifs/random"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)

    url = response.json()["data"]["images"]["original"]["url"]

    await update.message.reply_animation(
        animation=url,
    )
