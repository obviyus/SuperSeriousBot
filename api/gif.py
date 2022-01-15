from typing import Dict, TYPE_CHECKING

import requests

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def gif(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Get a random GIF from giphy"""
    params: Dict[str, str] = {"api_key": config["GIPHY_API_KEY"]}

    # TODO: Choose a better API, Giphy's results repeat a lot
    url: str = "http://api.giphy.com/v1/gifs/random"

    response: requests.Response = requests.get(url, params=params)
    url = response.json()["data"]["images"]["original"]["url"]

    update.message.reply_animation(
        animation=url,
    )
