from typing import Dict, Optional, TYPE_CHECKING

from requests import get

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def wink(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Reply with a wink GIF"""
    response(update.message, "wink")


def pat(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Reply with a pat GIF"""
    response(update.message, "pat")


def hug(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Reply with a hug GIF"""
    response(update.message, "hug")


def response(message: Optional["telegram.Message"], action: str):
    """Query API for appropriate action"""
    if not message:
        return

    r: Dict = get(f"https://some-random-api.ml/animu/{action}").json()

    if message.reply_to_message:
        message.reply_to_message.reply_animation(animation=r["link"])
    else:
        message.reply_animation(animation=r["link"])
