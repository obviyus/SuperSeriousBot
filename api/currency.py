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
            text="*Usage:* `/convert {AMOUNT} {FROM} {TO}`\n"
                 "*Example:* `/convert 300 USD EUR` \n\n"
                 "Defaults to `INR` if `TO` parameter not provided.",
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

    try:
        src_currency = word[1].upper()
    except IndexError:
        if amount.is_integer():
            amount = int(amount)
        output = f'{amount}? {amount} of what? Use /convert for usage.'
        bot.send_message(
            chat_id=message.chat_id,
            text=output,
            reply_to_message_id=message.message_id,
        )
        return

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
    except Exception:
        bot.send_message(
            chat_id=message.chat_id,
            text="Value too large :(",
            reply_to_message_id=message.message_id,
        )
        return
