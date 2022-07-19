from typing import Dict

import requests
from telegram import Update
from telegram.ext import ContextTypes

from config.options import config


async def gif(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random GIF from giphy"""
    params: Dict[str, str] = {"api_key": config["API"]["GIPHY_API_KEY"]}

    # TODO: Choose a better API, Giphy's results repeat a lot
    url: str = "https://api.giphy.com/v1/gifs/random"

    response: requests.Response = requests.get(url, params=params)
    url = response.json()["data"]["images"]["original"]["url"]

    await update.message.reply_animation(
        animation=url,
    )
