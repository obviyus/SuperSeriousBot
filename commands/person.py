import requests
from telegram import Update
from telegram.ext import ContextTypes


async def person(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a face from thispersondoesnotexist.com"""

    await update.message.reply_photo(
        photo=requests.get("https://thispersondoesnotexist.com/image").content
    )
