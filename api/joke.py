from requests import get
import time


def joke(update, context):
    """ Command to return a random joke"""

    response = get('https://sv443.net/jokeapi/v2/joke/Any')
    response = response.json()

    update.message.reply_text(text=response["setup"])
    time.sleep(2.0)
    context.bot.send_message(
        text=response["delivery"],
        chat_id=update.message.chat_id
    )
