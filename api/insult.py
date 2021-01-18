from requests import get
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram


def insult(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random insult"""

    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return
    response: dict = get('https://evilinsult.com/generate_insult.php?lang=en&type=json').json()

    if message.reply_to_message:
        message.reply_to_message.reply_text(text=response['insult'])
    else:
        message.reply_text(text=response['insult'])
