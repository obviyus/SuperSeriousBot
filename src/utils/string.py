from datetime import datetime

from telegram.ext import ContextTypes

from config.db import redis


async def readable_time(input_timestamp: int) -> str:
    """
    Return a readable time string.
    """
    seconds = abs(round(datetime.now().timestamp()) - input_timestamp)

    if seconds < 60:
        return f"{seconds} second" + ("s" if seconds > 1 else "")
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1g} minute" + ("s" if minutes > 1 else "")
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1g} hour" + ("s" if hours > 1 else "")
    elif seconds < 604800:
        days = seconds / 86400
        return f"{days:.1g} day" + ("s" if days > 1 else "")
    elif seconds < 31536000:
        weeks = seconds / 604800
        return f"{weeks:.1g} week" + ("s" if weeks > 1 else "")
    else:
        years = seconds / 31536000
        return f"{years:.1g} year" + ("s" if years > 1 else "")


async def get_username(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Get the username and/or first_name for a user_id.
    """
    username = redis.get(f"user_id:{user_id}")
    if username:
        return username
    else:
        chat = await context.bot.get_chat(user_id)
        if chat.username:
            redis.set(f"user_id:{user_id}", chat.username)
            return chat.username
        else:
            return chat.first_name


async def get_first_name(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Get the first_name for a user_id.
    """
    chat = await context.bot.get_chat(user_id)
    return chat.first_name


async def get_user_id_from_username(username: str) -> int | None:
    """
    Get the user_id from a username.
    """
    user_id = redis.get(f"username:{username.replace('@', '')}")
    return int(user_id) if user_id else None
