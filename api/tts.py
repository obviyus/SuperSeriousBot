from telegram import Update, Bot
from gtts import gTTS

def tts(bot: Bot, update: Update):
    message = update.message
    try:
        sentence = message.text.strip().split(' ', 1)[1]
    except IndexError:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/hltb {GAME_NAME}`\n*Example:* `/hltb horizon zero dawn`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return

    tts = gTTS(sentence, lang='en')
    tts_url = tts.get_urls()[0]

    bot.send_audio(
        chat_id=message.chat_id,
        audio = tts_url,
        performer="Udit",
        reply_to_message_id=message.message_id
    )