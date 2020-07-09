from googletrans import Translator
from telegram import Update, Bot


def translate(bot: Bot, update: Update):
    message = update.message
    sentence, dest = "", ""
    if len(message.text.strip().split(' ', 2)) >= 2:
        sentence = message.text.strip().split(' ', 1)[1]
    else:
        bot.send_message(
            chat_id=message.chat_id,
            # blame Udit for this example
            text="*Usage:* `/tl {DEST} - {SENTENCE}`\n*Example:* `/tl en - watashi wa anato no suki desu`\nDefaults to "
                 "`en` if none provided.",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )

    try:
        if '-' in sentence.split(' '):
            to_translate = sentence.split(' ', 2)[2]
            dest = sentence.split(' ', 2)[0]
        else:
            to_translate = sentence.split(' ', 2)[0]
    except IndexError:
        bot.send_message(
            chat_id=message.chat_id,
            text="No value provided.",
            reply_to_message_id=message.message_id,
        )
        return
    translator = Translator()
    if dest == "":
        translated = translator.translate(to_translate)
    else:
        try:
            translated = translator.translate(to_translate, dest=dest)
        except ValueError:
            bot.send_message(
                chat_id=message.chat_id,
                text="Invalid language.",
                reply_to_message_id=message.message_id,
            )
            return

    output = translated.text

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
    )
