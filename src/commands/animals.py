from typing import Callable, Dict, Tuple, Union

from requests import get
from telegram import MessageEntity, Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage


@triggers(["fox", "shiba", "cat"])
@description("Get a random image of the animal.")
@usage("/fox, /shiba, /cat")
@example("/fox, /shiba, /cat")
async def animal(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get animal"""

    animal_choice = None
    if update.message.caption:
        animal_choice = list(
            update.message.parse_caption_entities([MessageEntity.BOT_COMMAND]).values()
        )[0]
    elif update.message.text:
        animal_choice = list(
            update.message.parse_entities([MessageEntity.BOT_COMMAND]).values()
        )[0]

    if not animal_choice:
        await update.message.reply_text("No animal specified.")
        return

    animal_choice = animal_choice.partition("@")[0]
    urls: Dict[str, Tuple[str, Callable]] = {
        "/shiba": (
            "https://shibe.online/api/shibes?count=1&urls=true&httpsUrls=false",
            lambda resp: update.message.reply_photo(resp[0]),
        ),
        "/fox": (
            "https://randomfox.ca/floof/",
            lambda resp: update.message.reply_photo(resp["image"]),
        ),
        "/cat": (
            "https://api.thecatapi.com/v1/images/search",
            lambda resp: update.message.reply_photo(resp[0]["url"]),
        ),
    }

    response: Union[list, dict] = get(urls[animal_choice][0]).json()
    await urls[animal_choice][1](response)
