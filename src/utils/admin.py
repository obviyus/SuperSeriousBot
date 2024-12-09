from config.options import config


async def is_admin(user_id: str) -> bool:
    """
    Check if a user ID is in the admin list

    Args:
        user_id: Telegram user ID to check

    Returns:
        bool: True if user is admin, False otherwise
    """
    try:
        print(user_id, config["TELEGRAM"]["ADMINS"])
        return str(user_id) in config["TELEGRAM"]["ADMINS"]
    except (ValueError, TypeError):
        return False
