from datetime import datetime

from telegram import Message, MessageEntity
from telegram.constants import ParseMode

command_usage = {
    "seen": {
        "description": "Get the last time a user was seen.",
        "usage": "/seen [username]",
        "example": "/seen @obviyus",
    },
    "dl": {
        "description": "Download the media attached to a link.",
        "usage": "/dl [url]",
        "example": "/dl https://youtu.be/oOc1Bp01Buo",
    },
    "c": {
        "description": "Get the top Reddit comment for a link.",
        "usage": "/c [url]",
        "example": "/c https://youtu.be/dQw4w9WgXcQ",
    },
}


async def usage_string(message: Message) -> None:
    """
    Return the usage string for a command.
    """
    command = (
        list(message.parse_entities(MessageEntity.BOT_COMMAND).values())[0]
        .partition("@")[0][1:]
        .lower()
    )

    await message.reply_text(
        f"{command_usage[command]['description']}\n\n<b>Usage:</b>\n<pre>{command_usage[command]['usage']}</pre>\n\n<b>Example:</b>\n<pre>{command_usage[command]['example']}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def readable_time(input_timestamp: int) -> str:
    """
    Return a readable time string.
    """
    seconds = abs(round(datetime.now().timestamp()) - input_timestamp)

    if seconds < 60:
        return f"{seconds} second" + ("s" if seconds > 1 else "")
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute" + ("s" if minutes > 1 else "")
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour" + ("s" if hours > 1 else "")
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day" + ("s" if days > 1 else "")
    elif seconds < 31536000:
        weeks = seconds // 604800
        return f"{weeks} week" + ("s" if weeks > 1 else "")
    else:
        years = seconds // 31536000
        return f"{years} year" + ("s" if years > 1 else "")
