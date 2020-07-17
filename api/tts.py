from gtts import gTTS


def tts(update, context):
    """Command to convert text to speech in a given language using Google TTS."""
    message = update.message

    if not context.args:
        context.bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/tts {LANG} - {SENTENCE}`\n"
                 "*Example:* `/tts ru - cyka blyat`\n"
                 "Defaults to `ja` if none provided.",
        )
    else:
        if context.args[1:2] == ['-']:
            lang = context.args[0]
            sentence = ' '.join(context.args[2:])
        else:
            lang = "ja"
            sentence = ' '.join(context.args)

        if not sentence:
            context.bot.send_message(
                chat_id=message.chat_id,
                text="No value provided."
            )
        else:
            try:
                tts = gTTS(sentence, lang=lang)
                context.bot.send_audio(
                    chat_id=message.chat_id,
                    audio=tts.get_urls()[0]
                )
            except ValueError:
                context.bot.send_message(
                    chat_id=message.chat_id,
                    text="Invalid language."
                )
