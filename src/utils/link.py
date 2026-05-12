from urllib.parse import ParseResult, urlparse

from telegram import Message, MessageEntity


def grab_links(message: Message) -> dict[MessageEntity, str]:
    types: list[str | None] = [MessageEntity.URL, MessageEntity.TEXT_LINK]
    results = message.parse_entities(types=types)
    results.update(message.parse_caption_entities(types=types))
    for entity in results:
        if entity.type == MessageEntity.TEXT_LINK and entity.url:
            results[entity] = entity.url
    return results


def extract_link(message: Message) -> ParseResult | None:
    results = grab_links(message)
    if not results and message.reply_to_message:
        results = grab_links(message.reply_to_message)

    for _, url in sorted(results.items(), key=lambda item: item[0].offset):
        return urlparse(url)
    return None
