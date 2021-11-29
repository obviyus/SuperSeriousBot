from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from telegram import MessageEntity

from .reddit import reddit_parser
# from .youtube import youtube_parser

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def link_handler(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Forward URL to the appropriate handler"""
    if not update.message:
        return
    else:
        message: 'telegram.Message' = update.message

    text: str
    link_in_message: str

    entity_dict: dict = message.parse_entities([MessageEntity.URL, MessageEntity.TEXT_LINK])
    entity: MessageEntity = list(entity_dict.keys())[0]
    entity_text: str = list(entity_dict.values())[0]

    if entity.type == MessageEntity.TEXT_LINK and entity.url:
        link_in_message = entity.url
    else:
        link_in_message = entity_text

    split_url = urlsplit(link_in_message)

    hostname = split_url.hostname

    if hostname == 'www.reddit.com' or hostname == 'reddit.com':
        text = reddit_parser(link_in_message)
        update.message.reply_text(text=text)
    # TODO: find another yt parser
    # elif hostname == 'www.youtube.com' or hostname == 'youtube.com':
    #     text = youtube_parser(link_in_message)
    #     update.message.reply_text(text=text)
    else:
        return
