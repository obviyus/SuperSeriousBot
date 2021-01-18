from requests import get
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import telegram


def wink(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Reply with a wink GIF"""
    response(update.message, 'wink')


def pat(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Reply with a pat GIF"""
    response(update.message, 'pat')


def hug(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Reply with a hug GIF"""
    response(update.message, 'hug')


def response(message: Optional['telegram.Message'], action: str):
    """Query API for appropriate action"""
    if not message:
        return

    response = get(f'https://some-random-api.ml/animu/{action}').json()

    if message.reply_to_message:
        message.reply_to_message.reply_animation(animation=response['link'])
    else:
        message.reply_animation(animation=response['link'])
