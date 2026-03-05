from config.logger import logger
from config.options import config


def is_admin(user_id: int | str) -> bool:
    """
    Check if a user ID is in the admin list

    Args:
        user_id: Telegram user ID to check

    Returns:
        bool: True if user is admin, False otherwise
    """
    logger.debug("Admin check for user_id=%s", user_id)
    return str(user_id) in config["TELEGRAM"]["ADMINS"]
