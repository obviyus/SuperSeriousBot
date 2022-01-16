import random
import time
from typing import Dict, TYPE_CHECKING

from requests import get

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def joke(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random joke"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    response: Dict = get("https://v2.jokeapi.dev/joke/Any?type=twopart").json()
    punchline: str = response["delivery"]

    message.reply_text(text=response["setup"])
    time.sleep(2.0)

    context.bot.send_message(text=punchline[:-1] + " 😆", chat_id=message.chat_id)

    # Randomly say this
    if random.random() < 0.01:
        time.sleep(2.0)
        context.bot.send_message(
            text="Please don’t kick me 👉👈", chat_id=message.chat_id
        )
