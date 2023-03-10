from config.db import sqlite_conn


async def reset_command_limits() -> None:
    """
    Reset command limits for all users.
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE user_command_limits SET current_usage = 0 WHERE current_usage > 0;
        """
    )

    sqlite_conn.commit()
