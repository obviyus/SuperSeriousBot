from requests import get
from telegram import Update
from telegram.ext import ContextTypes


async def insult(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random insult"""
    insult_response: str = get(
        "https://evilinsult.com/generate_insult.php?lang=en&type=json"
    ).json()["insult"]

    if update.message.reply_to_message:
        await update.message.reply_to_message.reply_text(text=insult_response)
    else:
        await update.message.reply_text(text=insult_response)
