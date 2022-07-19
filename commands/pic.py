from random import choices

import requests
from telegram import InputMediaPhoto, Update
from telegram.ext import ContextTypes


async def pic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get random images from imgur"""
    chars: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghiklmnopqrstuvwxyz"
    length: int = 5

    try:
        n: int = int(context.args[0]) if context.args else 1
        # Request maximum 5 images at once
        n = min(n, 5)
    except ValueError:
        n = 1

    media_group = []
    while n > 0:
        address: str = (
            "https://i.imgur.com/" + "".join(choices(chars, k=length)) + ".jpg"
        )
        r = requests.get(address)

        # Ignore any images < 1000B
        if r.url == address and int(r.headers["content-length"]) > 1000:
            media_group.append(InputMediaPhoto(media=address))
            n -= 1

    await update.message.reply_media_group(
        media=media_group,
    )
