from __future__ import annotations

import importlib
import io
import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import libsql
from telegram import MessageEntity

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

chat_memory = importlib.import_module("management.chat_memory")
db = importlib.import_module("config.db")
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

    async def test_turso_adapter_matches_aiosqlite_call_shape(self):
        conn = db.TursoConnection(libsql.connect(":memory:", autocommit=True))

        await conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        cursor = await conn.execute(
            "INSERT INTO items (name) VALUES (?)",
            ("one",),
        )
        self.assertEqual(cursor.lastrowid, 1)
        self.assertEqual(cursor.rowcount, 1)

        async with conn.execute("SELECT id, name FROM items") as rows:
            row = await rows.fetchone()

        self.assertEqual(row["id"], 1)
        self.assertEqual(row[1], "one")

    async def test_turso_adapter_binds_datetimes_as_sqlite_text(self):
        conn = db.TursoConnection(libsql.connect(":memory:", autocommit=True))
        seen_at = datetime(2026, 6, 5, 7, 58, 2, 221759)

        await conn.execute("CREATE TABLE sightings (seen_at TEXT NOT NULL)")
        await conn.execute("INSERT INTO sightings (seen_at) VALUES (?)", (seen_at,))

        async with conn.execute("SELECT seen_at FROM sightings") as rows:
            row = await rows.fetchone()

        self.assertEqual(row["seen_at"], "2026-06-05 07:58:02.221759")


if __name__ == "__main__":
    unittest.main()
