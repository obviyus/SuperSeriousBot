from typing import TYPE_CHECKING

import regex

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def sed(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Use regex to search and replace text in messages you reply to"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    if (
            message
            and message.reply_to_message
            and (message.reply_to_message.text or message.reply_to_message.caption)
    ):
        string: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
        _, search, replace = message.text.split('/', 2)  # type: ignore

        result = regex.sub(search, replace, string, regex.POSIX)

        reply = f"{result}" if result else ""

        message.reply_to_message.reply_text(text=reply)
