"""
Common functionality between functions.
"""

from .cleaner import scrub_dict, scrub_html_tags
from .link import extract_link, grab_links
from .messages import get_message


async def readable_time(input_timestamp: int) -> str:
    from .string import readable_time as _readable_time

    return await _readable_time(input_timestamp)


async def get_username(user_id: int, context) -> str:
    from .string import get_username as _get_username

    return await _get_username(user_id, context)


async def get_first_name(user_id: int, context) -> str:
    from .string import get_first_name as _get_first_name

    return await _get_first_name(user_id, context)


async def get_user_id_from_username(username: str) -> int | None:
    from .string import get_user_id_from_username as _get_user_id_from_username

    return await _get_user_id_from_username(username)

__all__ = [
    "extract_link",
    "get_first_name",
    "get_message",
    "get_user_id_from_username",
    "get_username",
    "grab_links",
    "readable_time",
    "scrub_dict",
    "scrub_html_tags",
]
