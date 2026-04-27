from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils.decorators import command
from utils.messages import get_message

UD_API_URL = "https://api.urbandictionary.com/v0/define"
UD_WOTD_URL = "https://api.urbandictionary.com/v0/words_of_the_day"
MAX_DEFINITION_LENGTH = 1000


@command(
    triggers=["ud"],
    usage="/ud [word] or /ud (for Word of the Day)",
    example="/ud racism or /ud",
    description="Search a word on Urban Dictionary or get the Word of the Day.",
)
async def ud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not context.args:
        entries = await _fetch_ud_entries(UD_WOTD_URL)
        definition = entries[0] if entries else {}
        wotd_prefix = f"📅 Word of the Day ({definition.get('date', 'Today')}):\n\n"
    else:
        entries = await _fetch_ud_entries(
            UD_API_URL,
            {"term": " ".join(context.args).lower()},
        )
        definition = max(entries, key=lambda entry: entry["thumbs_up"]) if entries else {}
        wotd_prefix = ""

    if not definition:
        await message.reply_text("No results found.")
        return

    definition_text = truncate_text(definition["definition"])
    example_text = truncate_text(definition["example"])
    await message.reply_text(
        (
            f"{wotd_prefix}<a href='{definition['permalink']}'><b>{definition['word']}</b></a>\n\n"
            f"{definition_text}\n\n"
            f"<i>{example_text}</i>\n\n"
            f"<pre>👍 x {definition['thumbs_up']}</pre>"
        ),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def _fetch_ud_entries(url: str, params: dict | None = None) -> list[dict]:
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={"User-Agent": "SuperSeriousBot", "Accept": "application/json"},
            params=params,
        ) as response:
            if response.status != 200:
                return []
            data = await response.json()
    if "error" in data or not data.get("list"):
        return []
    return data["list"]



def truncate_text(text: str, max_length: int = MAX_DEFINITION_LENGTH) -> str:
    """Truncate text to a maximum length."""
    text = text.strip()
    return (text[:max_length] + "...") if len(text) > max_length else text
