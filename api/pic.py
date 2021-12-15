from random import choices
from typing import List, TYPE_CHECKING

import requests
import random
from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def pic(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get random images from imgur"""
    if not update.message:
        return

    albums = requests.get(
        f"https://api.imgur.com/3/gallery/random/random/{random.randint(0, 100000)}",
        headers={"Authorization": f"Client-ID {config['IMGUR_KEY']}"},
    ).json()["data"]
    random_album = random.choice(albums)
    try:
        image_url = random.choice(random_album["images"])["link"]
    except KeyError:
        # Some albums are just a single image
        image_url = random_album["link"]

    update.message.reply_photo(
        photo=image_url,
    )
