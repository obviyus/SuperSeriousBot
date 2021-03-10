import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Optional

import requests

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def goodreads(update: 'telegram.Update', context: 'telegram.ext.callbackcontext') -> None:
    """Query GoodReads for a book"""

    message: 'telegram.Message' = update.message
    query: str = ' '.join(context.args) if context.args else ''
    parse_mode: str = 'Markdown'

    if not query:
        text = "*Usage:*   `/gr {BOOK_NAME}`\n" \
               "*Example:* `/gr Clean Code`"
    else:
        response: requests.Response = requests.get(
            f'https://www.goodreads.com/search.xml?key={config["GOODREADS_API_KEY"]}&q={query}')
        book_id: str = ET.fromstring(response.content).findtext("search/results/work/best_book/id")

        if book_id:
            text = make_result(book_id)
            parse_mode = 'HTML'
        else:
            text = "No entry found."

    message.reply_text(
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=False,
    )


def make_result(goodreads_id: str) -> str:
    """Search using GoodReads ID of item"""

    response: requests.Response = requests.get(
        f'https://www.goodreads.com/book/show.xml?key={config["GOODREADS_API_KEY"]}&id={goodreads_id}')
    root: ET.Element = ET.fromstring(response.content)

    node: Optional[ET.Element] = root.find('book')
    title: str = node.findtext('title')
    isbn: str = node.findtext('isbn13')
    year: str = node.findtext('publication_year')
    author: str = node.findtext('authors/author/name')
    pages: str = node.find('num_pages').text
    url: str = node.find('url').text
    stars: str = f"⭐ {node.find('average_rating').text}"

    description: str = node.findtext('description').replace("<br />", "")
    description = description[:description.index('.', 200) + 1]

    cover_url: str = f"http://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"

    return f"<b>{title}</b> - ({year})\n" \
           f"<a href='{cover_url}'>&#8205;</a>" \
           f"{author}\n{stars} 📖 {pages} pages 🔗 <a href='{url}'>Goodreads</a>\n" \
           f"\n{description}"
