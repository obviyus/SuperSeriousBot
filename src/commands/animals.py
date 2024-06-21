from typing import Callable, Dict

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage

ANIMAL_APIS: Dict[str, tuple[str, Callable]] = {
    "shiba": (
        "https://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true",
        lambda data: data[0],
    ),
    "fox": ("https://randomfox.ca/floof/", lambda data: data["image"]),
    "cat": ("https://api.thecatapi.com/v1/images/search", lambda data: data[0]["url"]),
}


async def get_animal_url(session: aiohttp.ClientSession, animal: str) -> str:
    """Fetch animal image URL from the appropriate API."""
    url, extract_url = ANIMAL_APIS[animal]
    async with session.get(url) as response:
        data = await response.json()
        return extract_url(data)


@usage("/fox, /shiba, /cat")
@example("/fox, /shiba, /cat")
@triggers(["fox", "shiba", "cat"])
@description("Get a random image of the specified animal.")
async def animal(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle animal image request."""
    message = update.effective_message
    if not message:
        return

    command_entities = message.parse_entities(["bot_command"])
    if not command_entities:
        await message.reply_text("No animal specified.")
        return

    animal_choice = next(iter(command_entities.values())).lower().split("@")[0][1:]

    if animal_choice not in ANIMAL_APIS:
        await message.reply_text(f"Unknown animal: {animal_choice}")
        return

    async with aiohttp.ClientSession() as session:
        try:
            image_url = await get_animal_url(session, animal_choice)
            await message.reply_photo(image_url)
        except aiohttp.ClientError:
            await message.reply_text(
                f"Failed to fetch {animal_choice} image. Please try again later."
            )
