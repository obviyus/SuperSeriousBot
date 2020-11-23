from spurdify import spurdify


def spurdo(update, context):
    """Spurdify text"""
    message = update.message

    if not context.args:
        try:
            args = message.reply_to_message.text or message.reply_to_message.caption
            text = spurdify(args)
        except AttributeError:
            text = "*Usage:* `/spurdo {TEXT}`\n"\
                   "*Example:* `/spurdo hello, how are you?`\n"\
                   "Reply with `/spurdo` to a message to spurdify it."
    else:
        text = spurdify(' '.join(context.args))

    try:
        message.reply_to_message.reply_text(text=text)
    except AttributeError:
        message.reply_text(text=text)
