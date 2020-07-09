from telegram import Bot, Update
import wolframalpha

def calc(bot: Bot, update: Update):
    message = update.message
    try:
        query = message.text.strip().split(' ', 1)[1]
    except IndexError:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/calc {QUERY}`\n*Example:* `/calc 1 cherry ro grams`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return
    
    APP_ID = "GG7ARW-884TAXG48V"

    client = wolframalpha.Client(APP_ID)
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