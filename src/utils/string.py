from datetime import datetime

from async_lru import alru_cache
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config.db import get_db


async def readable_time(input_timestamp: int) -> str:
    seconds = abs(round(datetime.now().timestamp()) - input_timestamp)
    for limit, unit, divisor in (
        (60, "second", 1),
        (3600, "minute", 60),
        (86400, "hour", 3600),
        (604800, "day", 86400),
        (31536000, "week", 604800),
        (float("inf"), "year", 31536000),
    ):
        if seconds < limit:
            value = seconds / divisor
            return f"{value:.1f} {unit}".rstrip("0").rstrip(".") + (
                "s" if value > 1 else ""
            )
    return "0 seconds"


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

    try:
        chat = await context.bot.get_chat(user_id)
    except Exception:
        return f"{user_id}"

    if chat.username:
        async with get_db() as conn:
            await conn.execute(
                "INSERT INTO user_stats (user_id, username) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
                (user_id, chat.username),
            )
        return chat.username
    return chat.first_name or f"{user_id}"


@alru_cache(maxsize=128)
async def get_first_name(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        chat = await context.bot.get_chat(user_id)
    except BadRequest:
        return f"{user_id}"
    return chat.first_name or f"{user_id}"


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
