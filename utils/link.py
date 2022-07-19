from telegram import MessageEntity, Update


def extract_link(update: Update) -> str:
    """
    Extract the first URL from a given update.
    """

    if update.message.reply_to_message:
        url = update.message.reply_to_message.parse_entities(
            [MessageEntity.URL]
        ).values()
    elif update.message.text:
        url = update.message.parse_entities([MessageEntity.URL]).values()
    else:
        return ""

    url = next(iter(url), None)
    if not url:
        return ""

    return url
