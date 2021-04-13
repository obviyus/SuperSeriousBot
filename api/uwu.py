from typing import TYPE_CHECKING

import uwuify

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def uwu(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Spurdify text"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    flags = uwuify.SMILEY | uwuify.YU

    if not context.args:
        try:
            args: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
            text = uwuify.uwu(args, flags=flags)
        except AttributeError:
            text = "*Usage:* `/uwu {TEXT}`\n" \
                   "*Example:* `/uwu hello, how are you?`\n" \
                   "Reply with `/uwu` to a message to uwuify it."
    else:
        text = uwuify.uwu(' '.join(context.args), flags=flags)

    if message.reply_to_message:
        message.reply_to_message.reply_text(text=text)
    else:
        message.reply_text(text=text)
