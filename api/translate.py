from telegram import Update, Bot
from googletrans import Translator


def translate(bot: Bot, update: Update):
    message = update.message
    sentence = ""
    if len(message.text.strip().split(' ', 1)) >= 2:
        sentence = message.text.strip().split(' ', 1)[1]
    else:
        bot.send_message(
            chat_id=message.chat_id,
            # blame Udit for this example
            text="*Usage:* `/tl {SENTENCE}`\n*Example:* `/tl watashi wa anato no suki desu`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )

    translator = Translator()
    translated = translator.translate(sentence)
    source = translator.detect(sentence)

    output = translated.text

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
    )
