from collections.abc import Callable

from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import command

ANIMAL_APIS: dict[str, tuple[str, Callable]] = {
    "shiba": (
        "https://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true",
        lambda data: data[0],
    ),
    "fox": ("https://randomfox.ca/floof/", lambda data: data["image"]),
    "cat": ("https://api.thecatapi.com/v1/images/search", lambda data: data[0]["url"]),
}



@command(
    triggers=["fox", "shiba", "cat"],
    usage="/fox, /shiba, /cat",
    example="/fox, /shiba, /cat",
    description="Get a random image of the specified animal.",
)
async def animal(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle animal image request."""
    import aiohttp

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
            url, extract_url = ANIMAL_APIS[animal_choice]
            async with session.get(url) as response:
                data = await response.json()
            await message.reply_photo(extract_url(data))
        except aiohttp.ClientError:
            await message.reply_text(
                f"Failed to fetch {animal_choice} image. Please try again later."
            )
