from telegram import Bot, Update
import wolframalpha
from configuration import config

def calc(bot: Bot, update: Update):
    message = update.message
    try:
        query = message.text.strip().split(' ', 1)[1]
    except IndexError:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/calc {QUERY}`\n*Example:* `/calc 1 cherry to grams`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return

    client = wolframalpha.Client(config["WOLFRAM_APP_ID"])
    res = client.query(query)

    try:
        bot.send_message(
            chat_id=message.chat_id,
            text=next(res.results).text,
            reply_to_message_id=message.message_id,
        )
        return
    except AttributeError as e:
        pass
