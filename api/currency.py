import requests
from telegram import Bot, Update
from babel import numbers

def currency(bot: Bot, update: Update):
    message = update.message

    try:
        word = message.text.strip().split(' ', 1)[1].strip().split(' ', 3)
    except IndexError:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/convert {amount} {from} {to}`\n*Example:* `/convert 300 USD EUR`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return

    try:
        amount = float(word[0])
    except ValueError:
        bot.send_message(
            chat_id=message.chat_id,
            text="Not a number.",
            reply_to_message_id=message.message_id,
        )
        return

    src_currency = word[1].upper()

    if len(word) == 2:
        dest_currency = 'INR'
    else:
        dest_currency = word[2].upper()

    url = f'https://api.exchangeratesapi.io/latest?base={src_currency}'

    res = requests.get(url)
    result = res.json()

    try:
        rate = result['rates'][dest_currency]
        converted = rate * amount
        
        dest_symbol = numbers.format_currency(converted, dest_currency)

        bot.send_message(
            chat_id=message.chat_id,
            text=dest_symbol,
            reply_to_message_id=message.message_id,
            parse_mode='Markdown',
        )

    except KeyError:
        bot.send_message(
            chat_id=message.chat_id,
            text="No entry found.",
            reply_to_message_id=message.message_id,
        )
        return
