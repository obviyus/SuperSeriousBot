"""
Commands for chat management.
"""
from .stats import increment, get_chat_stats, get_last_seen
from .botstats import (
    get_total_chats,
    get_total_users,
    increment_command_count,
    get_command_stats,
)
