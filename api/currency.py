from requests import get
from babel import numbers


def currency(update, context):
    message = update.message

    if not context.args:
        text = "*Usage:* `/convert {AMOUNT} {FROM} {TO}`\n"\
               "*Example:* `/convert 300 USD EUR` \n\n"\
               "Defaults to `INR` if `TO` parameter not provided."
    else:
        amount, *currency = context.args

        try:
            amount = float(amount)
            # if its a number like 5.0 convert to 5
            if amount.is_integer():
                amount = int(amount)
        except ValueError:
            message.reply_text(text="Not a number.")
            return

        if not currency:
            text = f'{amount}? {amount} of what? Send /convert for usage.'
        else:
            src, *dest = currency
            dest, *_ = dest or ["INR"]  # magic

            result = get(f"https://api.exchangeratesapi.io/latest?base={src.upper()}")
            result = result.json()

            try:
                if dest.upper() in result["rates"]:
                    rate = result['rates'][dest.upper()]
                    converted = rate * amount

                    text = numbers.format_currency(converted, dest.upper())
                else:
                    text = "No entry found."
            except Exception:
                text = "Value too large :("

    message.reply_text(text=text)
