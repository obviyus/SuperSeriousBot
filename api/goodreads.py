from requests import get
from configuration import config
import xml.etree.ElementTree as ET
import isbnlib


def goodreads(update, context):
    """ Command to query GoodReads for a book"""
    message = update.message
    query = ' '.join(context.args)

    if not query:
        text = "*Usage:* `/gr {BOOK_NAME}`\n"\
               "*Example:* `/gr stoner`"
    else:
        response = get(f'https://www.goodreads.com/search.xml?key={config["GOODREADS_API_KEY"]}&q={query}')
        root = ET.fromstring(response.content)

        for node in root.iter('work'):
            if node is not None:
                title = node.find('best_book').find('title').text
                author = node.find('best_book').find('author').find('name').text
                # rating = node.find('average_rating').text
                cover = _cover_URL(title)
                stars = f"⭐ {node.find('average_rating').text}"

                text = f"<b>{title}</b>\n{author}\n{stars}"\
                       f"<a href='{cover}'>&#8205;</a>"

                break
            else:
                text="No entry found."

    message.reply_text(
        text=text,
        parse_mode='HTML',
        disable_web_page_preview=False,
    )

def _cover_URL(title: str):
    isbn = isbnlib.isbn_from_words(title)
    return f"http://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
