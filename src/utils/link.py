from typing import Dict
from urllib.parse import ParseResult, urlparse

from telegram import Message, MessageEntity


def grab_links(message: Message) -> dict[MessageEntity, str]:
    if not message:
        return {}

    types = [MessageEntity.URL, MessageEntity.TEXT_LINK]
    results = message.parse_entities(types=types)
    results.update(message.parse_caption_entities(types=types))

    return results


def extract_link(message: Message) -> ParseResult | None:
    """
    Extract the first URL from a given update.
    https://github.com/python-telegram-bot/ptbcontrib/blob/main/ptbcontrib/extract_urls/extracturls.py
    """
    if not message:
        return

    results = grab_links(message)
    if not results and message.reply_to_message:
        results = grab_links(message.reply_to_message)

    if not results:
        return

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

    try:
        return urlparse(sorted_results[0][0]) if sorted_results else None
    except IndexError:
        return None
