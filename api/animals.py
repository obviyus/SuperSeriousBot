from telegram import MessageEntity
from requests import get
from typing import TYPE_CHECKING, Dict, Tuple, Callable, Union

if TYPE_CHECKING:
    import telegram


def animal(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get animal"""
    if update.message:
        message = update.message
    else:
        return

    animal: str
    if update.message.caption:
        animal = list(update.message.parse_caption_entities([MessageEntity.BOT_COMMAND]).values())[0]
    elif update.message.text:
        animal = list(update.message.parse_entities([MessageEntity.BOT_COMMAND]).values())[0]

    urls: Dict[str, Tuple[str, Callable]] = {
        "/shiba": (
            'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=false',
            lambda resp: message.reply_photo(resp[0])
        ),
        "/fox": (
            'https://randomfox.ca/floof/',
            lambda resp: message.reply_photo(resp['image'])
        ),
        "/cat": (
            'https://api.thecatapi.com/v1/images/search',
            lambda resp: message.reply_photo(resp[0]['url'])
        ),
        "/catfact": (
            'https://cat-fact.herokuapp.com/facts/random',
            lambda resp: message.reply_text(resp['text'])
        ),
    }

    response: Union[list, dict] = get(urls[animal][0]).json()
    urls[animal][1](response)
