import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


@usage("/insult")
@example("/insult")
@triggers(["insult"])
@description("Send a random insult. Reply to a person to insult them.")
async def insult(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Get a random insult"""
    insult_response: str = ""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://evilinsult.com/generate_insult.php",
                params={"lang": "en", "type": "json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                insult_response = data.get("insult", "")
    except Exception:
        insult_response = "I'm too polite to insult right now."

    if message.reply_to_message:
        await message.reply_to_message.reply_text(text=insult_response)
    else:
        await message.reply_text(text=insult_response)
