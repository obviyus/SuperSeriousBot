import regex


def sed(update, context):
    """Use regex to search and replace text in messages you reply to"""
    message = update.message

    string = message.reply_to_message.text or message.reply_to_message.caption

    _, search, replace = message.text.split('/', 2)

    result = regex.sub(search, replace, string, regex.POSIX)

    reply = f"{result}" if result else ""
    message.reply_text(text=reply)
