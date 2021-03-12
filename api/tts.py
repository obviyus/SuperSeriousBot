from io import BytesIO
from typing import TYPE_CHECKING

from gtts import gTTS

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def tts(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Convert text to speech in a given language using Google TTS"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    lang: str
    if not context.args:
        try:
            sentence: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
            speech: gTTS = gTTS(sentence, lang='ja')
            with BytesIO() as fp:
                speech.write_to_fp(fp)
                fp.name = f'tts__{sentence[:10]}.ogg'
                fp.seek(0)
                message.reply_audio(audio=fp)
        except AttributeError:
            message.reply_text(
                text="*Usage:* `/tts {LANG} - {SENTENCE}`\n"
                     "*Example:* `/tts ru - cyka blyat`\n"
                     "Defaults to `ja` if none provided.\n"
                     "Reply with `/tts` to a message to speak it in Japanese.",
            )
            return
    else:
        # [1:2] will return first item or empty list if the index doesn't exist
        if context.args[1:2] == ['-']:
            lang = context.args[0]
            sentence = ' '.join(context.args[2:])
        else:
            lang = "ja"
            sentence = ' '.join(context.args)

        if not sentence:
            message.reply_text(text="No value provided.")
        else:
            try:
                speech = gTTS(sentence, lang=lang)
                with BytesIO() as fp:
                    speech.write_to_fp(fp)
                    fp.name = f'tts__{sentence[:10]}.ogg'
                    fp.seek(0)
                    message.reply_audio(audio=fp)
            except ValueError:
                message.reply_text(text="Invalid language.")
