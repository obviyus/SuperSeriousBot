import requests
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import telegram
    import telegram.ext


def meme(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random meme"""
    if not update.message:
        return

    url: str = requests.get("https://meme-api.herokuapp.com/gimme").json()["url"]
    if url.endswith(".gif"):
        update.message.reply_animation(
            animation=url,
        )
    else:
        update.message.reply_photo(photo=url)
