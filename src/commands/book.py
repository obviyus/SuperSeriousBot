import xml.etree.ElementTree as ET
from typing import Optional

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

GOODREADS_SEARCH_URL = "https://www.goodreads.com/search.xml"
GOODREADS_BOOK_URL = "https://www.goodreads.com/book/show.xml"
OPENLIBRARY_COVER_URL = "https://covers.openlibrary.org/b/isbn/{}-L.jpg"


@usage("/book [BOOK_TITLE]")
@example("/book The Hitchhiker's Guide to the Galaxy")
@triggers(["book"])
@api_key("GOODREADS_API_KEY")
@description("Search for a book on GoodReads.")
async def book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Query GoodReads for a book"""
    if not context.args:
        await commands.usage_string(update.message, book)
        return

    query: str = " ".join(context.args)
    async with aiohttp.ClientSession() as session:
        book_id = await _search_book(session, query)
        if not book_id:
            await update.message.reply_text("No book found.")
            return

        book_details = await _get_book_details(session, book_id)
        if not book_details:
            await update.message.reply_text("Failed to fetch book details.")
            return

        await update.message.reply_text(
            text=book_details,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )


async def _search_book(session: aiohttp.ClientSession, query: str) -> Optional[str]:
    """Search for a book and return its ID"""
    params = {"q": query, "key": config["API"]["GOODREADS_API_KEY"]}
    async with session.get(GOODREADS_SEARCH_URL, params=params) as response:
        if response.status != 200:
            return None
        root = ET.fromstring(await response.text())
        return root.findtext("search/results/work/best_book/id")


async def _get_book_details(
    session: aiohttp.ClientSession, book_id: str
) -> Optional[str]:
    """Fetch and format book details"""
    params = {"id": book_id, "key": config["API"]["GOODREADS_API_KEY"]}
    async with session.get(GOODREADS_BOOK_URL, params=params) as response:
        if response.status != 200:
            return None
        root = ET.fromstring(await response.text())
        book = root.find("book")
        if not book:
            return None

        title = book.findtext("title", "Unknown Title")
        isbn = book.findtext("isbn13", "")
        year = book.findtext("publication_year", "Unknown")
        author = book.findtext("authors/author/name", "Unknown Author")
        pages = book.findtext("num_pages", "Unknown")
        url = book.findtext("url", "")
        rating = book.findtext("average_rating", "0")
        book_description = book.findtext("description", "No description available.")

        book_description = utils.cleaner.scrub_html_tags(book_description)
        book_description = (
            book_description[: book_description.index(".", 200) + 1]
            if "." in book_description
            else book_description[:200]
        )

        cover_url = OPENLIBRARY_COVER_URL.format(isbn) if isbn else ""

        return (
            f"<b>{title}</b> - ({year})\n\n"
            f"<a href='{cover_url}'>&#8205;</a>"
            f"✏️ {author}\n⭐ {rating}\n📖 {pages} pages\n🔗 <a href='{url}'>Goodreads</a>\n"
            f"\n{book_description}"
        )
