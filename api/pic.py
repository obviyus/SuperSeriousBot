from random import choices
from typing import TYPE_CHECKING, List

import requests
from telegram import InputMediaPhoto

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def pic(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get random images from imgur"""
    if not update.message:
        return

    chars: str = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghiklmnopqrstuvwxyz'
    length: int = 5

    try:
        n: int = int(context.args[0]) if context.args else 1
        # Request maximum 5 images at once
        n = min(n, 5)
    except ValueError:
        n = 1

    media_group: List[InputMediaPhoto] = []
    while n > 0:
        address: str = 'https://i.imgur.com/' + "".join(choices(chars, k=length)) + '.jpg'
        r = requests.get(address)

        # Ignore any images < 1000B
        if r.url == address and int(r.headers['content-length']) > 1000:
            media_group.append(InputMediaPhoto(media=address))
            n -= 1

    update.message.reply_media_group(
        media=media_group,
    )
