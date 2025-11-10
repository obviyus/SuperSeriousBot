import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message

GOODREADS_API = {
    "SEARCH": "https://www.goodreads.com/search.xml",
    "BOOK": "https://www.goodreads.com/book/show.xml",
    "COVER": "https://covers.openlibrary.org/b/isbn/{}-L.jpg",
}


@dataclass
class BookDetails:
    """Book information container"""

    title: str = "Unknown Title"
    isbn: str = ""
    year: str = "Unknown"
    author: str = "Unknown Author"
    pages: str = "Unknown"
    url: str = ""
    rating: str = "0"
    description: str = "No description available."

    def format_message(self) -> str:
        """Format book details for Telegram message"""
        cover_url = GOODREADS_API["COVER"].format(self.isbn) if self.isbn else ""
        self.title = self.title.replace("- ()", "")

        return (
            f"<b>{self.title}</b> - ({self.year})\n\n"
            f"<a href='{cover_url}'>&#8205;</a>"
            f"✏️ {self.author}\n⭐ {self.rating}\n📖 {self.pages} pages\n"
            f"🔗 <a href='{self.url}'>Goodreads</a>\n\n"
            f"{self.description}"
        )


@lru_cache(maxsize=100)
async def _search_book(session: aiohttp.ClientSession, query: str) -> str | None:
    """Search for a book and return its ID with caching"""
    params = {"q": query, "key": config["API"]["GOODREADS_API_KEY"]}
    try:
        async with session.get(GOODREADS_API["SEARCH"], params=params) as response:
            if response.status != 200:
                return None
            root = ET.fromstring(await response.text())
            return root.findtext(".//work/best_book/id")
    except (ET.ParseError, aiohttp.ClientError):
        return None


def _truncate_description(desc: str, limit: int = 200) -> str:
    """Smartly truncate description at sentence boundary"""
    desc = utils.cleaner.scrub_html_tags(desc)
    if len(desc) <= limit:
        return desc

    sentence_end = desc.find(".", limit)
    return desc[: sentence_end + 1] if sentence_end != -1 else desc[:limit] + "..."


async def _get_book_details(
    session: aiohttp.ClientSession, book_id: str
) -> BookDetails | None:
    """Fetch and parse book details"""
    params = {"id": book_id, "key": config["API"]["GOODREADS_API_KEY"]}
    try:
        async with session.get(GOODREADS_API["BOOK"], params=params) as response:
            if response.status != 200:
                return None

            root = ET.fromstring(await response.text())
            book = root.find("book")
            if not book:
                return None

            details = BookDetails(
                title=book.findtext("title", BookDetails.title),
                isbn=book.findtext("isbn13", BookDetails.isbn),
                year=book.findtext("publication_year", BookDetails.year),
                author=book.findtext(".//authors/author/name", BookDetails.author),
                pages=book.findtext("num_pages", BookDetails.pages),
                url=book.findtext("url", BookDetails.url),
                rating=book.findtext("average_rating", BookDetails.rating),
                description=_truncate_description(
                    book.findtext("description", BookDetails.description)
                ),
            )
            return details

    except (ET.ParseError, aiohttp.ClientError):
        return None


@usage("/book [BOOK_TITLE]")
@example("/book The Hitchhiker's Guide to the Galaxy")
@triggers(["book"])
@api_key("GOODREADS_API_KEY")
@description("Search for a book on GoodReads.")
async def book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Query GoodReads for a book"""
    if not context.args:
        await commands.usage_string(message, book)
        return

    query: str = " ".join(context.args)
    async with aiohttp.ClientSession() as session:
        if book_id := await _search_book(session, query):
            if book_details := await _get_book_details(session, book_id):
                await message.reply_text(
                    text=book_details.format_message(),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                )
                return

        await message.reply_text("❌ No book found matching your query.")
