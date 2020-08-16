from requests import get
import time
import random


def joke(update, context):
    """Get a random joke"""

    # Randomly choose between these two APIs
    if random.random() < 0.5:
        response = get('https://sv443.net/jokeapi/v2/joke/Any')
    else:
        response = get('https://official-joke-api.appspot.com/random_joke')

    response = response.json()

    update.message.reply_text(text=response["setup"])
    time.sleep(2.0)

    try:
        punchline = response["delivery"]
    except KeyError:
        punchline = response["punchline"]

    context.bot.send_message(
        text=punchline[:-1] + " 😆",
        chat_id=update.message.chat_id
    )

    # Randomly say this
    if random.random() < 0.01:
        context.bot.send_message(
            text="Please don’t kick me 👉👈",
            chat_id=update.message.chat_id
        )
