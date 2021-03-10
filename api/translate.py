from typing import TYPE_CHECKING

from googletrans import Translator
from googletrans.models import Translated

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def translate(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Translate text to a given language using Google translate"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    if not context.args:
        try:
            args: str = message.reply_to_message.text or message.reply_to_message.caption
            translator: Translator = Translator()
            translated: Translated = translator.translate(args, dest='en')
            text = translated.__dict__()["text"]
        except AttributeError:
            text = "*Usage:* `/tl {DEST} - {SENTENCE}`\n" \
                   "*Example:* `/tl en - watashi wa anato no suki desu`\n" \
                   "Defaults to `en` if none provided.\n" \
                   "Reply with `/tl` to a message to translate it to english."

    else:
        # [1:2] will return first item or empty list if the index doesn't exist
        lang: str = "en"
        if context.args[1:2] == ['-']:
            lang = context.args[0]
            sentence = ' '.join(context.args[2:])
        else:
            sentence = ' '.join(context.args)

        if not sentence:
            text = "No value provided."
        else:
            translator = Translator()
            try:
                translated = translator.translate(sentence, dest=lang)
                text = translated.__dict__()["text"]
            except ValueError:
                text = "Invalid language."

    message.reply_text(text=text)
