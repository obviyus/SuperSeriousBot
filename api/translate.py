from googletrans import Translator


def translate(update, context):
    """Command to translate text in a given language using Google translate."""
    message = update.message

    if not context.args:
        # blame Udit for this example
        text = "*Usage:* `/tl {DEST} - {SENTENCE}`\n"\
               "*Example:* `/tl en - watashi wa anato no suki desu`\n"\
               "Defaults to `en` if none provided."
    else:
        # [1:2] will return first item or empty list if the index doesn't exist
        if context.args[1:2] == ['-']:
            lang = context.args[0]
            sentence = ' '.join(context.args[2:])
        else:
            lang = "en"
            sentence = ' '.join(context.args)

        if not sentence:
            text = "No value provided."
        else:
            translator = Translator()
            try:
                translated = translator.translate(sentence, dest=lang)
                text = translated.text
            except ValueError:
                text = "Invalid language."

    context.bot.send_message(chat_id=message.chat_id, text=text)
