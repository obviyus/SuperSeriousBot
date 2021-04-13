import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse, ParseResult

import pafy
from dateutil import parser

from configuration import config

pafy.set_api_key(config["YOUTUBE_API_KEY"])

from telegram import MessageEntity
import emoji

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def handle_youtube(url: str) -> str:
    video = pafy.new(url)

    duration: str = str(datetime.timedelta(seconds=video.length))
    views: str = "{:,}".format(video.viewcount)
    upload_date = parser.parse(video.published)

    return f"`{video.author} | {duration}`" \
           f"\n`{views} views`" \
           f"\n`{upload_date.date()}`" \
           f"""\n`{emoji.emojize(f":thumbs_up: × {video.likes} | :thumbs_down: × {video.dislikes}")}`"""


def link_handler(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Provide additional info for links"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return
    text: str

    link_in_message: str = list(message.parse_entities(MessageEntity.URL).values())[0]
    if link_in_message:
        parsed_url: ParseResult = urlparse(link_in_message)
        domain: str = '{uri.netloc}'.format(uri=parsed_url)

        if domain[:4] == "www.":
            domain = domain[4:]

        if domain == 'youtube.com' or domain == 'youtu.be':
            text = handle_youtube(link_in_message)
        else:
            return
        message.reply_text(text=text)
    else:
        return
