from telegram import Message
from telegram.ext import ContextTypes

from config.db import get_db
from utils.admin import is_admin

# Daily defaults for expensive / API-backed commands.
DEFAULT_DAILY_LIMITS: dict[str, int] = {
    "ask": 40,
    "edit": 20,
    "search": 30,
    "tldr": 30,
    "song": 8,
    "cron": 20,
    "tr": 40,
}


async def reset_command_limits(_: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_db() as conn:
        await conn.execute(
            """
            UPDATE user_command_limits SET current_usage = 0 WHERE current_usage > 0;
            """
        )


async def consume_command_quota(user_id: int, command: str) -> bool:
    """Increment usage for a limited command. Returns False if over daily limit."""
    default_limit = DEFAULT_DAILY_LIMITS.get(command)
    if default_limit is None or is_admin(user_id):
        return True

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, `limit`, current_usage
            FROM user_command_limits
            WHERE user_id = ? AND command = ?
            ORDER BY id
            LIMIT 1
            """,
            (user_id, command),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await conn.execute(
                """
                INSERT INTO user_command_limits (user_id, command, `limit`, current_usage)
                VALUES (?, ?, ?, 1)
                """,
                (user_id, command, default_limit),
            )
            return True

        limit = int(row["limit"]) if row["limit"] else default_limit
        if int(row["current_usage"]) >= limit:
            return False

        claim = await conn.execute(
            """
            UPDATE user_command_limits
            SET current_usage = current_usage + 1
            WHERE id = ? AND current_usage < ?
            """,
            (row["id"], limit),
        )
        return claim.rowcount > 0


async def ensure_quota(message: Message, user_id: int, command: str) -> bool:
    if await consume_command_quota(user_id, command):
        return True
    await message.reply_text(
        "Daily limit for this command reached. Try again tomorrow."
    )
    return False
