from datetime import datetime

from telegram import Message, MessageEntity
from telegram.constants import ParseMode

command_usage = {
    "seen": {
        "usage": "/seen <username>",
        "example": "/seen @obviyus",
    },
    "dl": {
        "usage": "/dl <url>",
        "example": "/dl https://www.youtube.com/watch?v=oOc1Bp01Buo",
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
        f"""
        <b>Usage:</b> {command_usage[command]["usage"]}
        <b>Example:</b> {command_usage[command]["example"]}
        """,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def readable_time(input_timestamp: int) -> str:
    """
    Return a readable time string.
    """
    seconds = round(datetime.now().timestamp()) - input_timestamp
    tense = "ago" if seconds >= 0 else "from now"

    seconds = abs(seconds)

    if seconds < 60:
        return f"{seconds} second" + ("s" if seconds > 1 else "") + f" {tense}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute" + ("s" if minutes > 1 else "") + f" {tense}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour" + ("s" if hours > 1 else "") + f" {tense}"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day" + ("s" if days > 1 else "") + f" {tense}"
    elif seconds < 31536000:
        weeks = seconds // 604800
        return f"{weeks} week" + ("s" if weeks > 1 else "") + f" {tense}"
    else:
        years = seconds // 31536000
        return f"{years} year" + ("s" if years > 1 else "") + f" {tense}"
