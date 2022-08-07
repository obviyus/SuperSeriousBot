import random
import time

from requests import get
from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage


@usage("/joke")
@example("/joke")
@triggers(["joke"])
@description("Get a two part joke.")
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random joke"""
    response = get("https://v2.jokeapi.dev/joke/Any?type=twopart").json()
    punchline = response["delivery"]

    await update.message.reply_text(text=response["setup"])
    time.sleep(2.0)

    await context.bot.send_message(
        text=punchline[:-1] + " 😆", chat_id=update.message.chat_id
    )

    # Say this 1% of the time
    if random.random() < 0.01:
        time.sleep(2.0)
        await context.bot.send_message(
            text="Please don’t kick me 👉👈", chat_id=update.message.chat_id
        )
