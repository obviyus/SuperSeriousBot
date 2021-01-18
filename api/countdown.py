from datetime import datetime
import dateparser
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import datetime as dt
    import telegram


def countdown(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Show days left till a date"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return
    countdown_to: str = ' '.join(context.args) if context.args else ''

    text: str
    if not countdown_to:
        text = "*Usage:* `/countdown {WHENEVER}`\n"\
               "*Example:* `/countdown 9 november`"
    else:
        future: Optional[datetime] = dateparser.parse(countdown_to)

        if future:
            delta: 'dt.timedelta' = future - datetime.now()
            text = f"{abs(delta.days)} days {'a' if delta.days < 0 else 'to '}go"
        else:
            text = "Invalid date format"

    message.reply_text(text=text)
