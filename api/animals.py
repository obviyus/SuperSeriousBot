from requests import get
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram


def shiba(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random Shiba Inu image"""

    response: list = get('http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=false').json()
    if update.message:
        update.message.reply_photo(response[0])


def fox(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random Fox image"""

    response: dict = get('https://randomfox.ca/floof/').json()
    if update.message:
        update.message.reply_photo(response['image'])


def cat(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random Cat image"""

    response: list = get('https://api.thecatapi.com/v1/images/search').json()
    if update.message:
        update.message.reply_photo(response[0]['url'])


def catfact(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get a random Cat Fact"""

    response: dict = get('https://cat-fact.herokuapp.com/facts/random').json()
    if update.message:
        update.message.reply_text(response["text"])
