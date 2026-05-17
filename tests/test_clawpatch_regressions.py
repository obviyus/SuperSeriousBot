from __future__ import annotations

import io
import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram import MessageEntity

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")

chat_memory = importlib.import_module("management.chat_memory")
send_markdown_or_plain = importlib.import_module(
    "utils.messages"
).send_markdown_or_plain


class FakeBot:
    def __init__(self) -> None:
        self.sent_message = None
        self.sent_document = None

    async def send_message(self, **kwargs):
        self.sent_message = kwargs

    async def send_document(self, **kwargs):
        document = kwargs["document"]
        assert isinstance(document, io.BytesIO)
        self.sent_document = {
            "chat_id": kwargs["chat_id"],
            "name": document.name,
            "text": document.getvalue().decode(),
        }


class ClawpatchRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_markdown_or_plain_uses_document_for_long_plain_text(self):
        bot = FakeBot()

        await send_markdown_or_plain(
            bot,
            123,
            "x" * 5000,
            document_name="long.txt",
        )

        self.assertIsNone(bot.sent_message)
        self.assertEqual(bot.sent_document["chat_id"], 123)
        self.assertEqual(bot.sent_document["name"], "long.txt")
        self.assertEqual(bot.sent_document["text"], "x" * 5000)

    async def test_process_mentions_uses_telegram_entity_parser(self):
        entity = SimpleNamespace(type=MessageEntity.MENTION)
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=1),
            entities=[entity],
            text="😀 @knownuser",
            reply_to_message=None,
            parse_entity=lambda parsed_entity: "@knownuser",
        )

        with (
            patch.object(
                chat_memory,
                "get_user_id_from_username",
                AsyncMock(return_value=2),
            ) as get_user_id,
            patch.object(chat_memory, "save_mention", AsyncMock()) as save_mention,
        ):
            await chat_memory.process_mentions(message)

        get_user_id.assert_awaited_once_with("knownuser")
        save_mention.assert_awaited_once_with(1, 2, message)


if __name__ == "__main__":
    unittest.main()
