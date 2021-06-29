from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from telegram import MessageEntity

from .reddit import reddit_parser
from .youtube import youtube_parser

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def link_handler(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Forward URL to the appropriate handler"""
    if not update.message:
        return
    else:
        message: 'telegram.Message' = update.message

    text: str
    link_in_message = list(message.parse_entities([MessageEntity.URL]).values())[0]
    split_url = urlsplit(link_in_message)

    hostname = split_url.hostname

    if hostname == 'www.reddit.com' or hostname == 'reddit.com':
        text = reddit_parser(link_in_message)
        update.message.reply_text(text=text)
    elif hostname == 'www.youtube.com' or hostname == 'youtube.com':
        text = youtube_parser(link_in_message)
        update.message.reply_text(text=text)
    else:
        return
