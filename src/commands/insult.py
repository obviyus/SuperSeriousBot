from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["insult"],
    usage="/insult",
    example="/insult",
    description="Send a random insult. Reply to a person to insult them.",
)
async def insult(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    import httpx2

    message = get_message(update)
    if not message:
        return
    insult_response: str = ""
    try:
        async with httpx2.AsyncClient(follow_redirects=True) as session:
            resp = await session.get(
                "https://evilinsult.com/generate_insult.php",
                params={"lang": "en", "type": "json"},
                timeout=httpx2.Timeout(10),
            )
            data = resp.json()
            insult_response = data.get("insult", "")
    except (httpx2.HTTPError, TimeoutError, ValueError):
        insult_response = "I'm too polite to insult right now."

    if message.reply_to_message:
        await message.reply_to_message.reply_text(text=insult_response)
    else:
        await message.reply_text(text=insult_response)
