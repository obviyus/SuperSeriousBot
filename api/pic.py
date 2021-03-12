from random import choices
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def pic(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random image from imgur"""
    if not update.message:
        return

    chars: str = '01234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghiklmnopqrstuvwxyz'
    length: int = 5

    while True:
        address: str = 'https://i.imgur.com/' + "".join(choices(chars, k=length)) + '.jpg'
        if requests.get(address).url == address:
            break

    update.message.reply_photo(
        photo=address,
    )
