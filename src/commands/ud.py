import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage
from utils.messages import get_message

UD_API_URL = "https://api.urbandictionary.com/v0/define"
UD_WOTD_URL = "https://api.urbandictionary.com/v0/words_of_the_day"
MAX_DEFINITION_LENGTH = 1000


@triggers(["ud"])
@usage("/ud [word] or /ud (for Word of the Day)")
@example("/ud racism or /ud")
@description("Search a word on Urban Dictionary or get the Word of the Day.")
async def ud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Search a word on Urban Dictionary or get the Word of the Day."""
    if not context.args:
        definition = await fetch_ud_wotd()
        wotd_prefix = f"📅 Word of the Day ({definition.get('date', 'Today')}):\n\n"
    else:
        query = " ".join(context.args).lower()
        definition = await fetch_ud_definition(query)
        wotd_prefix = ""

    if not definition:
        await message.reply_text("No results found.")
        return

    formatted_definition = format_ud_definition(definition, wotd_prefix)
    await message.reply_text(
        formatted_definition,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def fetch_ud_definition(word: str) -> dict:
    """Fetch definition from Urban Dictionary API."""
    headers = {
        "User-Agent": "SuperSeriousBot",
        "Accept": "application/json",
    }
    params = {"term": word}

    async with aiohttp.ClientSession() as session:
        async with session.get(UD_API_URL, headers=headers, params=params) as response:
            if response.status != 200:
                return {}
            data = await response.json()
            if "error" in data or not data.get("list"):
                return {}
            return max(data["list"], key=lambda x: x["thumbs_up"])


async def fetch_ud_wotd() -> dict:
    """Fetch Word of the Day from Urban Dictionary API."""
    headers = {
        "User-Agent": "SuperSeriousBot",
        "Accept": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(UD_WOTD_URL, headers=headers) as response:
            if response.status != 200:
                return {}
            data = await response.json()
            if not data or not data.get("list"):
                return {}
            return data["list"][0]  # Return the first word of the day from the list


def format_ud_definition(result: dict, prefix: str = "") -> str:
    """Format the Urban Dictionary definition."""
    definition = truncate_text(result["definition"])
    ud_example = truncate_text(result["example"])

    return (
        f"{prefix}<a href='{result['permalink']}'><b>{result['word']}</b></a>\n\n"
        f"{definition}\n\n"
        f"<i>{ud_example}</i>\n\n"
        f"<pre>👍 x {result['thumbs_up']}</pre>"
    )


def truncate_text(text: str, max_length: int = MAX_DEFINITION_LENGTH) -> str:
    """Truncate text to a maximum length."""
    text = text.strip()
    return (text[:max_length] + "...") if len(text) > max_length else text
