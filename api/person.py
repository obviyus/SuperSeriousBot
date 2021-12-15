import requests
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import telegram
    import telegram.ext


def person(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a face from thispersondoesnotexist.com"""
    if not update.message:
        return

    update.message.reply_photo(
        photo=requests.get("https://thispersondoesnotexist.com/image").content
    )
