import xml.etree.ElementTree as ET

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage


@triggers(["book"])
@description("Search for a book on GoodReads.")
@usage("/book")
@example("/book")
@api_key("GOODREADS_API_KEY")
async def book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Query GoodReads for a book"""

    if not context.args:
        await commands.usage_string(update.message, book)
        return

    query: str = " ".join(context.args)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.goodreads.com/search.xml",
            params={"q": query, "key": config["API"]["GOODREADS_API_KEY"]},
        )

    book_id = ET.fromstring(response.content).findtext(
        "search/results/work/best_book/id"
    )

    text = ""
    if book_id:
        text = await make_result(book_id)

    if not text:
        text = "No entry found."

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False,
    )


async def make_result(goodreads_id: str) -> str:
    """Search using GoodReads ID of item"""

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.goodreads.com/book/show.xml",
            params={"id": goodreads_id, "key": config["API"]["GOODREADS_API_KEY"]},
        )

    root = ET.fromstring(response.content)
    node = root.find("book")
    if not node:
        return ""

    title = node.findtext("title")
    isbn = node.findtext("isbn13")
    year = node.findtext("publication_year")
    author = node.findtext("authors/author/name")
    pages = node.findtext("num_pages")
    url = node.findtext("url")
    stars = f"""⭐ {node.findtext("average_rating")}"""

    description = utils.cleaner.scrub_html_tags(node.findtext("description"))
    description = description[: description.index(".", 200) + 1].replace(".", ". ")

    cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"

    return (
        f"<b>{title}</b> - ({year})\n\n"
        f"<a href='{cover_url}'>&#8205;</a>"
        f"✏️{author}\n{stars}\n📖 {pages} pages\n🔗 <a href='{url}'>Goodreads</a>\n"
        f"\n{description}"
    )
