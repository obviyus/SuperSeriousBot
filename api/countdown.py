from telegram import Update, Bot
from datetime import datetime
import dateparser

def countdown(bot: Bot, update: Update):
    message = update.message
    try:
        to = message.text.strip().split(' ', 1)[1]
    except IndexError:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/hltb {GAME_NAME}`\n*Example:* `/hltb horizon zero dawn`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return

    future = dateparser.parse(to)
    today = datetime.now()

    delta = future - today

    if delta.days > 0:
        otuput = f'{delta.days} days to go'
        bot.send_message(
            chat_id=message.chat_id,
            text=otuput,
            reply_to_message_id=message.message_id,
            parse_mode='Markdown',
        )
    else:
        bot.send_message(
            chat_id=message.chat_id,
            text=f'{abs(delta.days)} days ago',
            reply_to_message_id=message.message_id,
        )
        return
