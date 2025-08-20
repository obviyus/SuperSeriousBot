import asyncio
import random

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage


@usage("/joke")
@example("/joke")
@triggers(["joke"])
@description("Get a two part joke.")
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random joke"""
    setup = "Here's a joke..."
    punchline = "(joke delivery unavailable)"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://v2.jokeapi.dev/joke/Any",
                params={"type": "twopart"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                setup = data.get("setup", setup)
                punchline = data.get("delivery", punchline)
    except Exception:
        pass

    await update.message.reply_text(text=setup)
    await asyncio.sleep(2.0)

    await context.bot.send_message(
        text=punchline[:-1] + " 😆", chat_id=update.message.chat_id
    )

    # Say this 1% of the time
    if random.random() < 0.01:
        await asyncio.sleep(2.0)
        await context.bot.send_message(
            text="Please don’t kick me 👉👈", chat_id=update.message.chat_id
        )
