import httpx
from telegram import Update
from telegram.ext import ContextTypes


async def person(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a face from thispersondoesnotexist.com"""

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://thispersondoesnotexist.com/image",
        )

    await update.message.reply_photo(photo=response.content)
