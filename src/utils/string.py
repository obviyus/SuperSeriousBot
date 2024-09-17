from datetime import datetime

from async_lru import alru_cache
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config.db import get_db


async def readable_time(input_timestamp: int) -> str:
    """
    Return a readable time string.
    """
    seconds = abs(round(datetime.now().timestamp()) - input_timestamp)

    if seconds < 60:
        return "{0:.1f} second".format(seconds).rstrip("0").rstrip(".") + (
            "s" if seconds > 1 else ""
        )
    elif seconds < 3600:
        minutes = seconds / 60
        return "{0:.1f} minute".format(minutes).rstrip("0").rstrip(".") + (
            "s" if minutes > 1 else ""
        )
    elif seconds < 86400:
        hours = seconds / 3600
        return "{0:.1f} hour".format(hours).rstrip("0").rstrip(".") + (
            "s" if hours > 1 else ""
        )
    elif seconds < 604800:
        days = seconds / 86400
        return "{0:.1f} day".format(days).rstrip("0").rstrip(".") + (
            "s" if days > 1 else ""
        )
    elif seconds < 31536000:
        weeks = seconds / 604800
        return "{0:.1f} week".format(weeks).rstrip("0").rstrip(".") + (
            "s" if weeks > 1 else ""
        )
    else:
        years = seconds / 31536000
        return "{0:.1f} year".format(years).rstrip("0").rstrip(".") + (
            "s" if years > 1 else ""
        )


@alru_cache(maxsize=128)
async def get_username(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Get the username and/or first_name for a user_id.
    """
    async with get_db() as conn:
        async with conn.execute(
            "SELECT username FROM user_stats WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            result = await cursor.fetchone()

    if result and result["username"]:
        return result["username"]
    else:
        chat = await context.bot.get_chat(user_id)
        if chat.username:
            async with get_db(write=True) as conn:
                await conn.execute(
                    "INSERT INTO user_stats (user_id, username) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
                    (user_id, chat.username),
                )
            return chat.username
        elif chat.first_name:
            return chat.first_name
        else:
            return f"{user_id}"


@alru_cache(maxsize=128)
async def get_first_name(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Get the first_name for a user_id.
    """
    try:
        chat = await context.bot.get_chat(user_id)
    except BadRequest:
        return f"{user_id}"

    return chat.first_name


@alru_cache(maxsize=128)
async def get_user_id_from_username(username: str) -> int | None:
    """
    Get the user_id from a username.
    """
    async with get_db() as conn:
        async with conn.execute(
            "SELECT user_id FROM user_stats WHERE LOWER(username) = ?",
            (username.lower().replace("@", ""),),
        ) as cursor:
            result = await cursor.fetchone()

    return int(result["user_id"]) if result else None
