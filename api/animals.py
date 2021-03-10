from typing import TYPE_CHECKING, Dict, Tuple, Callable, Union

from requests import get
from telegram import MessageEntity

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def animal(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get animal"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    animal: str
    if update.message.caption:
        animal = list(message.parse_caption_entities([MessageEntity.BOT_COMMAND]).values())[0]
    elif update.message.text:
        animal = list(message.parse_entities([MessageEntity.BOT_COMMAND]).values())[0]

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
