import html
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.options import config
from utils.decorators import command
from utils.messages import get_message

GOODREADS_API = {
    "SEARCH": "https://www.goodreads.com/search.xml",
    "BOOK": "https://www.goodreads.com/book/show.xml",
    "COVER": "https://covers.openlibrary.org/b/isbn/{}-L.jpg",
}


@command(
    triggers=["book"],
    usage="/book [BOOK_TITLE]",
    example="/book The Hitchhiker's Guide to the Galaxy",
    description="Search for a book on GoodReads.",
    api_key="GOODREADS_API_KEY",
)
async def book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import aiohttp

    message = get_message(update)
    if not message:
        return
    if not context.args:
        await commands.usage_string(message, book)
        return

    params = {"q": " ".join(context.args), "key": config.API.GOODREADS_API_KEY}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(GOODREADS_API["SEARCH"], params=params) as response:
                if response.status != 200:
                    await message.reply_text("❌ No book found matching your query.")
                    return
                root = ET.fromstring(await response.text())
                book_id = root.findtext(".//work/best_book/id")
            if not book_id:
                await message.reply_text("❌ No book found matching your query.")
                return

            async with session.get(
                GOODREADS_API["BOOK"],
                params={"id": book_id, "key": config.API.GOODREADS_API_KEY},
            ) as response:
                if response.status != 200:
                    await message.reply_text("❌ No book found matching your query.")
                    return
                root = ET.fromstring(await response.text())
        except (ET.ParseError, aiohttp.ClientError):
            await message.reply_text("❌ No book found matching your query.")
            return

    book_data = root.find("book")
    if not book_data:
        await message.reply_text("❌ No book found matching your query.")
        return

    title = book_data.findtext("title", "Unknown Title").replace("- ()", "")
    isbn = book_data.findtext("isbn13", "")
    cover_url = GOODREADS_API["COVER"].format(isbn) if isbn else ""
    description = utils.cleaner.scrub_html_tags(
        book_data.findtext("description", "No description available.")
    )
    if len(description) > 200:
        sentence_end = description.find(".", 200)
        description = (
            description[: sentence_end + 1]
            if sentence_end != -1
            else description[:200] + "..."
        )
    book_url = book_data.findtext("url", "")
    if urlparse(book_url).scheme not in {"http", "https"}:
        book_url = ""
    await message.reply_text(
        text=(
            f"<b>{html.escape(title)}</b> - ({html.escape(book_data.findtext('publication_year', 'Unknown'))})\n\n"
            f"<a href='{html.escape(cover_url, quote=True)}'>&#8205;</a>"
            f"✏️ {html.escape(book_data.findtext('.//authors/author/name', 'Unknown Author'))}\n"
            f"⭐ {html.escape(book_data.findtext('average_rating', '0'))}\n"
            f"📖 {html.escape(book_data.findtext('num_pages', 'Unknown'))} pages\n"
            f"🔗 <a href='{html.escape(book_url, quote=True)}'>Goodreads</a>\n\n"
            f"{html.escape(description)}"
        ),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False,
    )
