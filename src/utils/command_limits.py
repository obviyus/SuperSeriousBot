from telegram.ext import ContextTypes

from config.db import get_db


async def reset_command_limits(_: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reset command limits for all users.
    """
    async with get_db(write=True) as conn:
        await conn.execute(
            """
            UPDATE user_command_limits SET current_usage = 0 WHERE current_usage > 0;
            """
        )

        await conn.commit()
