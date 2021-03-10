import random
import time
from typing import TYPE_CHECKING, Dict

from requests import get

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def joke(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random joke"""

    # Randomly choose between these two APIs
    response: Dict
    if random.random() < 0.5:
        response = get('https://sv443.net/jokeapi/v2/joke/Any').json()
    else:
        response = get('https://official-joke-api.appspot.com/random_joke').json()

    text: str
    punchline: str

    update.message.reply_text(text=response["setup"])
    time.sleep(2.0)

    try:
        punchline = response["delivery"]
    except KeyError:
        punchline = response["punchline"]

    # Workaround to prevent last letter being replaced
    if punchline[-1] != '.':
        punchline += '.'

    context.bot.send_message(
        text=punchline[:-1] + " 😆",
        chat_id=update.message.chat_id
    )

    time.sleep(2.0)

    # Randomly say this
    if random.random() < 0.01:
        context.bot.send_message(
            text="Please don’t kick me 👉👈",
            chat_id=update.message.chat_id
        )
