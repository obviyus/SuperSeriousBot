from collections.abc import Mapping
from typing import TypeGuard

from telegram import Update
from telegram.ext import ContextTypes

from config.options import config
from utils.decorators import command
from utils.messages import get_message

KLIPY_API_URL = "https://api.klipy.com/api/v1/{api_key}/gifs/trending"
KLIPY_MEDIA_FORMATS = ("gif", "mediumgif", "tinygif", "nanogif", "preview")


def is_json_object(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


def klipy_gif_url(data: object) -> str | None:
    if not is_json_object(data):
        return None

    payload = data.get("data")
    if not is_json_object(payload):
        return None

    items = payload.get("data")
    if not isinstance(items, list) or not items:
        return None

    import random

    item = random.choice(items)
    if not is_json_object(item):
        return None

    files = item.get("files")
    if not is_json_object(files):
        return None

    for media_format in KLIPY_MEDIA_FORMATS:
        rendition = files.get(media_format)
        if is_json_object(rendition):
            url = rendition.get("url")
            if isinstance(url, str):
                return url

    return None


@command(
    triggers=["gif"],
    usage="/gif",
    example="/gif",
    description="Get a random GIF.",
    api_key="KLIPY_API_KEY",
)
async def gif(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    import aiohttp

    message = get_message(update)
    if not message:
        return

    if not config.API.KLIPY_API_KEY:
        await message.reply_text("GIFs are not configured.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                KLIPY_API_URL.format(api_key=config.API.KLIPY_API_KEY),
                params={"per_page": 24, "rating": "g", "locale": "en_US"},
            ) as response:
                if response.status != 200:
                    await message.reply_text("Could not fetch a GIF right now.")
                    return
                data = await response.json()
    except aiohttp.ClientError:
        await message.reply_text("Could not fetch a GIF right now.")
        return

    gif_url = klipy_gif_url(data)
    if not gif_url:
        await message.reply_text("Could not fetch a GIF right now.")
        return

    await message.reply_animation(animation=gif_url)
