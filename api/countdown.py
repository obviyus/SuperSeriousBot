from datetime import datetime
import dateparser


def countdown(update, context):
    """Command to show days left till a date."""
    message = update.message
    countdown_to = ' '.join(context.args)

    if not countdown_to:
        text = "*Usage:* `/countdown {WHENEVER}`\n"\
               "*Example:* `/countdown 9 november`"
    else:
        future = dateparser.parse(countdown_to)

        if future:
            delta = future - datetime.now()
            text = f"{abs(delta.days)} days {'a' if delta.days < 0 else 'to '}go"
        else:
            text = "Invalid date format"

    context.bot.send_message(chat_id=message.chat_id, text=text)
