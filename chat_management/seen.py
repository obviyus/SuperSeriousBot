from typing import TYPE_CHECKING

import redis
from datetime import datetime

if TYPE_CHECKING:
    import telegram
    import telegram.ext

r = redis.StrictRedis(host='redis', port='6379', db=0, charset="utf-8", decode_responses=True)


def seen(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get how long ago last message from a user was in a group"""
    if not update.message:
        return
    else:
        message = update.message

    text: str

    if not context.args:
        text = "*Usage:* `/seen @{username}`\n" \
               "*Example:* `/seen @obviyus`"
    else:
        username = context.args[0].replace('@', '')
        r_get = r.get(f"seen:{username}")
        if not r_get:
            text = f"No messages recorded from @{username}"
        else:
            last_seen: datetime = datetime.fromisoformat(r_get)

            difference = (datetime.now() - last_seen).total_seconds()
            duration: str

            if difference < 60:
                duration = str(difference) + ' seconds'
            elif difference < 3600:
                duration = str(difference // 60) + ' minutes'
            elif difference < 86400:
                duration = str(difference // 3600) + ' hours'
            else:
                duration = str(difference // 86400) + ' days'
            text = f"{username}'s last message was {duration} ago"

    message.reply_text(text, parse_mode=None)
