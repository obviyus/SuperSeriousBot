from typing import TYPE_CHECKING

from requests import get

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def insult(update: "telegram.Update", _context: "telegram.ext.CallbackContext") -> None:
    """Get a random insult"""

    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    insult_response: str = get(
        "https://evilinsult.com/generate_insult.php?lang=en&type=json"
    ).json()["insult"]
    if message.reply_to_message:
        message.reply_to_message.reply_text(text=insult_response)
    else:
        message.reply_text(text=insult_response)
