from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

class Client:
    def __init__(self, session_name: str, api_id: str, api_hash: str) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def search_messages(
        self,
        chat_id: int,
        from_user: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AsyncIterator[Any]: ...
    async def delete_messages(
        self, chat_id: int, message_ids: Sequence[int]
    ) -> None: ...
