from telegram import Update, Bot
from gtts import gTTS


def tts(bot: Bot, update: Update):
    lang, to_speak, sentence = "ja", "", ""
    message = update.message

    if len(message.text.strip().split(' ', 2)) >= 2:
        sentence = message.text.strip().split(' ', 1)[1]
    else:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/tts {LANG} - {SENTENCE}`\n"
                 "*Example:* `/tts ru - cyka blyat`\n"
                 "Defaults to `ja` if none provided.",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return

    try:
        if '-' in sentence.split(' '):
            to_speak = sentence.split(' ', 2)[2]
            lang = sentence.split(' ', 2)[0]
        else:
            to_speak = sentence
    except (IndexError, AssertionError):
        bot.send_message(
            chat_id=message.chat_id,
            text='No value provided.',
            reply_to_message_id=message.message_id
        )
        return

    tts = gTTS(to_speak, lang=lang)

    bot.send_audio(
        chat_id=message.chat_id,
        audio=tts.get_urls()[0],
        reply_to_message_id=message.message_id,
        parse_mode='Markdown',
    )
