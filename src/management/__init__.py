"""
Commands for chat management.
"""
from .botstats import (
    get_command_stats,
    get_total_chats,
    get_total_users,
    get_uptime,
    increment_command_count,
)
from .stats import get_chat_stats, get_last_seen, increment
