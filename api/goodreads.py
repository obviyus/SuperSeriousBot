from requests import get
from configuration import config
import xml.etree.ElementTree as ET


def goodreads(update, context):
    """ Command to query GoodReads for a book"""
    message = update.message
    query = ' '.join(context.args)
    parse_mode = 'Markdown'

    if not query:
        text = "*Usage:*   `/gr {BOOK_NAME}`\n"\
               "*Example:* `/gr stoner`"
    else:
        response = get(f'https://www.goodreads.com/search.xml?key={config["GOODREADS_API_KEY"]}&q={query}')
        root = ET.fromstring(response.content)
        id = root.findtext("search/results/work/best_book/id")

        if id:
            text = make_result(id)
            parse_mode = 'HTML'
        else:
            text = "No entry found."

    message.reply_text(
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=False,
    )


def make_result(goodreads_id):
    """ Search using Goodreads ID of item """
    r = get(f'https://www.goodreads.com/book/show.xml?key={config["GOODREADS_API_KEY"]}&id={goodreads_id}')
    root = ET.fromstring(r.content)

    node = root.find('book')
    title = node.findtext('title')
    isbn = node.findtext('isbn13')
    year = node.findtext('publication_year')
    author = node.findtext('authors/author/name')

    description = node.findtext('description').replace("<br />", "")
    description = description[:description.index('.', 200) + 1]

    cover_url = f"http://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
    pages = node.find('num_pages').text
    url = node.find('url').text
    stars = f"⭐ {node.find('average_rating').text}"

    return f"<b>{title}</b> - ({year})\n"\
           f"<a href='{cover_url}'>&#8205;</a>"\
           f"{author}\n{stars} 📖 {pages} pages 🔗 <a href='{url}'>Goodreads</a>\n"\
           f"\n{description}"
