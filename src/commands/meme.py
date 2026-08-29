from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import command
from utils.messages import get_message

MEME_API_URL = "https://meme-api.com/gimme"
MEME_FETCH_ATTEMPTS = 5


@command(
    triggers=["meme"],
    usage="/meme",
    example="/meme",
    description="Get a random meme.",
)
async def meme(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return

    import httpx2

    try:
        async with httpx2.AsyncClient(
            timeout=httpx2.Timeout(10), follow_redirects=True
        ) as session:
            url = None
            for _ in range(MEME_FETCH_ATTEMPTS):
                response = await session.get(MEME_API_URL)
                if response.status_code != 200:
                    await message.reply_text("Could not fetch a meme right now.")
                    return
                data = response.json()
                if data.get("nsfw"):
                    continue
                url = data.get("url")
                if url:
                    break
            if not url:
                await message.reply_text("Could not fetch a SFW meme right now.")
                return
    except (httpx2.HTTPError, KeyError, TypeError):
        await message.reply_text("Could not fetch a meme right now.")
        return

    if url.endswith(".gif"):
        await message.reply_animation(
            animation=url,
        )
    else:
        await message.reply_photo(photo=url)
