import requests
from telegram import Bot, Update
from babel import numbers

def currency(bot: Bot, update: Update):
    message = update.message
    word = message.text.strip().split(' ', 1)[1].strip().split(' ', 2)

    amount = float(word[0])
    src_currency = word[1]
    dest_currency = "INR"

    url = f'https://api.exchangeratesapi.io/latest?base={src_currency}'

    res = requests.get(url)
    result = res.json()

    if not result['rates']:
        bot.send_message(
            chat_id=message.chat_id,
            text="No entry found.",
            reply_to_message_id=message.message_id,
        )
        return
    
    rate = result['rates'][dest_currency]
    converted = rate * amount

    dest_symbol = numbers.format_currency(converted, dest_currency)

    bot.send_message(
        chat_id=message.chat_id,
        text=dest_symbol,
        reply_to_message_id=message.message_id,
        parse_mode='Markdown',
    )
