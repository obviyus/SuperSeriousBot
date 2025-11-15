from __future__ import annotations

from enum import Enum

class ChatType(str, Enum):
    PRIVATE: ChatType
    BOT: ChatType
    SUPERGROUP: ChatType
    CHANNEL: ChatType
