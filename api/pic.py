from requests import get
from random import choices
from PIL import Image
from io import BytesIO


def pic(update, context):
    """Get a random image from imgur"""
    chars = '01234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghiklmnopqrstuvwxyz'
    length = 5

    while True:
        img_code = choices(chars, k=length)
        address = 'https://i.imgur.com/' + "".join(img_code) + '.jpg'
        img = Image.open(BytesIO(get(address).content))

        if img.size[0] != 161:
            break

    context.bot.send_photo(
        photo=address,
        chat_id=update.message.chat_id
    )
