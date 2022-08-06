from turtle import update
from typing import Dict
from urllib.parse import ParseResult, urlparse

from telegram import MessageEntity, Update


def extract_link(update: Update) -> ParseResult | None:
    """
    Extract the first URL from a given update.
    https://github.com/python-telegram-bot/ptbcontrib/blob/main/ptbcontrib/extract_urls/extracturls.py
    """
    if not update.message:
        return None

    message = (
        update.message.reply_to_message
        if update.message.reply_to_message
        else update.message
    )

    types = [MessageEntity.URL, MessageEntity.TEXT_LINK]
    results = message.parse_entities(types=types)
    results.update(message.parse_caption_entities(types=types))

    # Get the actual urls
    for key in results:
        if key.type == MessageEntity.TEXT_LINK:
            results[key] = key.url

    # Remove exact duplicates and keep the first appearance
    filtered_results: Dict[str, MessageEntity] = {}
    for key, value in results.items():
        if not filtered_results.get(value):
            filtered_results[value] = key
        else:
            if key.offset < filtered_results[value].offset:
                filtered_results[value] = key

    # Sort results by order of appearance, i.e. the MessageEntity offset
    sorted_results = sorted(filtered_results.items(), key=lambda e: e[1].offset)

    return urlparse(sorted_results[0][0]) if sorted_results else None
