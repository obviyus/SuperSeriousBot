from gtts import gTTS


def tts(update, context):
    """Command to convert text to speech in a given language using Google TTS."""
    message = update.message

    if not context.args:
        message.reply_text(
            text="*Usage:* `/tts {LANG} - {SENTENCE}`\n"
                 "*Example:* `/tts ru - cyka blyat`\n"
                 "Defaults to `ja` if none provided.",
        )
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
                message.reply_audio(audio=tts.get_urls()[0])
            except ValueError:
                message.reply_text(text="Invalid language.")
