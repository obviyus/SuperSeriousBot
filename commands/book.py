import xml.etree.ElementTree as ET

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config.options import config


async def book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Query GoodReads for a book"""

    if not context.args:
        await utils.usage_string(update.message)
        return

    query: str = " ".join(context.args)
    response = requests.get(
        "https://www.goodreads.com/search.xml",
        params={"q": query, "key": config["API"]["GOODREADS_API_KEY"]},
    )

    book_id = ET.fromstring(response.content).findtext(
        "search/results/work/best_book/id"
    )

    if book_id:
        text = make_result(book_id)
    else:
        text = "No entry found."

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False,
    )


def make_result(goodreads_id: str) -> str:
    """Search using GoodReads ID of item"""

    response = requests.get(
        "https://www.goodreads.com/search.xml",
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
    pages = node.find("num_pages")
    pages = pages.text if pages else ""
    url = node.find("url")
    url = url.text if url else ""
    stars = node.find("average_rating")
    stars = f"⭐ {stars.text}" if stars else ""

    description = node.findtext("description").replace("<br />", "")
    description = description[: description.index(".", 200) + 1]

    cover_url = f"http://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"

    return (
        f"<b>{title}</b> - ({year})\n"
        f"<a href='{cover_url}'>&#8205;</a>"
        f"{author}\n{stars} 📖 {pages} pages 🔗 <a href='{url}'>Goodreads</a>\n"
        f"\n{description}"
    )
