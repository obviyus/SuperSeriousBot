from spurdify import spurdify
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram


def spurdo(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Spurdify text"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    if not context.args:
        try:
            args: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
            text = spurdify(args)
        except AttributeError:
            text = "*Usage:* `/spurdo {TEXT}`\n"\
                   "*Example:* `/spurdo hello, how are you?`\n"\
                   "Reply with `/spurdo` to a message to spurdify it."
    else:
        text = spurdify(' '.join(context.args))

    if message.reply_to_message:
        message.reply_to_message.reply_text(text=text)
    else:
        message.reply_text(text=text)
