from telegram import Update, Bot
from gtts import gTTS


def tts(bot: Bot, update: Update):
    message = update.message
    sentence, lang, to_speak = "", "", ""
    if len(message.text.strip().split(' ', 2)) >= 2:
        sentence = message.text.strip().split(' ', 1)[1]
    else:
        bot.send_message(
            chat_id=message.chat_id,
            # blame Udit for this example
            text="*Usage:* `/tts {LANG} - {SENTENCE}`\n*Example:* `/tl ru - cyka blyat`\nDefaults to "
                 "`en` if none provided.",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )

    try:
        if '-' in sentence.split(' '):
            to_speak = sentence.split(' ', 2)[2]
            lang = sentence.split(' ', 2)[0]
        else:
            to_speak = sentence.split(' ', 2)[0]
            lang = 'en'
    except (IndexError, AssertionError) as e:
        bot.send_audio(
            chat_id=message.chat_id,
            title='translate_tts',
            file_id='tts',
            audio='https://archive.org/download/NeverGonnaGiveYouUp/jocofullinterview41.mp3',
            reply_to_message_id=message.message_id
        )
        return

    tts = gTTS(to_speak, lang=lang)
    tts_url = tts.get_urls()[0]

    bot.send_audio(
        chat_id=message.chat_id,
        audio=tts_url,
        performer="Udit",
        reply_to_message_id=message.message_id
    )
