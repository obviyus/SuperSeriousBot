import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import config
from utils.decorators import api_key, description, example, triggers, usage


@usage("/meme")
@example("/meme")
@triggers(["meme"])
@description("Get a random meme.")
async def meme(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random meme"""
    if not update.message:
        return

    async with httpx.AsyncClient() as client:
        response = await client.get("https://meme-api.herokuapp.com/gimme")

    url: str = response.json()["url"]
    if url.endswith(".gif"):
        await update.message.reply_animation(
            animation=url,
        )
    else:
        await update.message.reply_photo(photo=url)


@usage("/tyag")
@example("/tyag")
@triggers(["tyag"])
@api_key("STEAM_API_KEY")
@description("Get Elden Ring playtime for @MyTransformerIsFine.")
async def tyag(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get Elden Ring playtime for @MyTransformerIsFine."""
    with httpx.Client() as client:
        response = client.get(
            "https://decapi.me/steam/hours/76561198090799457/1245620",
            params={"key": config["API"]["STEAM_API_KEY"]},
        )
        response_readable = client.get(
            "https://decapi.me/steam/hours/76561198090799457/1245620/readable",
            params={"key": config["API"]["STEAM_API_KEY"]},
        )

        await update.message.reply_text(
            text=f"@MyTransformerIsFine has played Elden Ring for <b>{response.text}</b> ({response_readable.text.strip()}).",
            parse_mode=ParseMode.HTML,
        )


@usage("/kinji")
@example("/kinji")
@triggers(["kinji"])
@api_key("STEAM_API_KEY")
@description("Get Destiny 2 playtime for @tumadrehomo.")
async def kinji(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get Destiny 2 playtime for @tumadrehomo."""
    with httpx.Client() as client:
        response = client.get(
            "https://decapi.me/steam/hours/76561198217369533/1085660",
            params={"key": config["API"]["STEAM_API_KEY"]},
        )
        response_readable = client.get(
            "https://decapi.me/steam/hours/76561198217369533/1085660/readable",
            params={"key": config["API"]["STEAM_API_KEY"]},
        )

        await update.message.reply_text(
            text=f"@tumadrehomo has played Destiny 2 for <b>{response.text}</b> ({response_readable.text.strip()}).",
            parse_mode=ParseMode.HTML,
        )


@usage("/udit")
@example("/udit")
@triggers(["udit"])
@api_key("STEAM_API_KEY")
@description("Get Destiny 2 playtime for @WeirdIndianBoi.")
async def udit(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get Destiny 2 playtime for @WeirdIndianBoi."""
    with httpx.Client() as client:
        response = client.get(
            "https://decapi.me/steam/hours/76561198405571182/730",
            params={"key": config["API"]["STEAM_API_KEY"]},
        )
        response_readable = client.get(
            "https://decapi.me/steam/hours/76561198405571182/730/readable",
            params={"key": config["API"]["STEAM_API_KEY"]},
        )

        await update.message.reply_text(
            text=f"@WeirdIndianBoi has played CSGO for <b>{response.text}</b> ({response_readable.text.strip()}).",
            parse_mode=ParseMode.HTML,
        )
