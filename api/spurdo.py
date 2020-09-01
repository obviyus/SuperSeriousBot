from requests import get
from urllib.parse import urlencode


def spurdo(update, context):
    """Convert text to spurdo"""
    message = update.message
    if not context.args:
        try:
            args = message.reply_to_message.text or message.reply_to_message.caption
            message.reply_to_message.reply_text(text=spurdo_request(args))
        except AttributeError:
            message.reply_text(
                text="*Usage:* `/spurdo {TEXT}`\n"
                     "*Example:* `/spurdo hello world`\n"
            )
            return
    else:
        sentence = ' '.join(context.args)
        message.reply_text(text=spurdo_request(sentence))


def spurdo_request(text):
    payload = {'text': text}
    url = "https://spurdo.pste.pw/?" + urlencode(payload)
    return get(url).text
