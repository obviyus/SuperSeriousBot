import asyncio
import random

from telegram import Update
from telegram.ext import ContextTypes

from config.logger import logger
from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["joke"],
    usage="/joke",
    example="/joke",
    description="Get a two part joke.",
)
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import httpx2

    message = get_message(update)
    if not message:
        return
    setup = "Here's a joke..."
    punchline = "(joke delivery unavailable)"
    try:
        async with httpx2.AsyncClient(follow_redirects=True) as session:
            resp = await session.get(
                "https://v2.jokeapi.dev/joke/Any",
                params={"type": "twopart"},
                timeout=httpx2.Timeout(10),
            )
            data = resp.json()
            setup = data.get("setup", setup)
            punchline = data.get("delivery", punchline)
    except (httpx2.HTTPError, TimeoutError, ValueError) as exc:
        logger.debug("Joke API unavailable: %s", exc)

    await message.reply_text(text=setup)
    await asyncio.sleep(2.0)

    await context.bot.send_message(text=punchline[:-1] + " 😆", chat_id=message.chat_id)

    # Say this 1% of the time
    if random.random() < 0.01:
        await asyncio.sleep(2.0)
        await context.bot.send_message(
            text="Please don't kick me 👉👈", chat_id=message.chat_id
        )
