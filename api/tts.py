from gtts import gTTS
from io import BytesIO


def tts(update, context):
    """Convert text to speech in a given language using Google TTS"""
    message = update.message
    if not context.args:
        try:
            sentence = message.reply_to_message.text or message.reply_to_message.caption
            tts = gTTS(sentence, lang='ja')
            with BytesIO() as fp:
                tts.write_to_fp(fp)
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
                tts = gTTS(sentence, lang=lang)
                with BytesIO() as fp:
                    tts.write_to_fp(fp)
                    fp.name = f'tts__{sentence[:10]}.ogg'
                    fp.seek(0)
                    message.reply_audio(audio=fp)
            except ValueError:
                message.reply_text(text="Invalid language.")
