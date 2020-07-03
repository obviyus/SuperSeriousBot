from telegram import Update, Bot
from googletrans import Translator


def translate(bot: Bot, update: Update):
    message = update.message
    sentence = message.text.strip().split(' ', 1)[1]

    translator = Translator()
    translated = translator.translate(sentence)
    source = translator.detect(sentence)

    output = translated.text

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
    )
