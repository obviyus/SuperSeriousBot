from __future__ import annotations

import datetime
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import libsql
from telegram.error import ChatMigrated, TimedOut

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

db = importlib.import_module("config.db")
migrate = importlib.import_module("migrate")
remind = importlib.import_module("commands.remind")


class ConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return None


def reminders_database(path: str):
    connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
    connection.execute(
        """
        CREATE TABLE reminders (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_time INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    migration = migrate.load_migration(
        Path("migrations/20260726030000_reminder_delivery_leases.py")
    )
    migration.upgrade(connection)
    return connection


async def run_worker(connection, bot: AsyncMock) -> None:
    wrapped = db.TursoConnection(connection)
    try:
        with patch.object(
            remind,
            "get_db",
            return_value=ConnectionContext(wrapped),
        ):
            await remind.worker_reminder(SimpleNamespace(bot=bot))
    finally:
        await wrapped.close()


class ReminderTests(unittest.IsolatedAsyncioTestCase):
    def test_ist_relative_time_uses_kolkata_offset(self):
        now = datetime.datetime(2026, 7, 26, 12, tzinfo=datetime.UTC)

        target = remind.parse_reminder_time("tomorrow 9am IST", now=now)

        self.assertEqual(
            target,
            datetime.datetime(2026, 7, 27, 3, 30, tzinfo=datetime.UTC),
        )

    def test_ambiguous_weekday_prefers_the_future(self):
        now = datetime.datetime(2026, 7, 26, 12, tzinfo=datetime.UTC)

        target = remind.parse_reminder_time("Monday 9am", now=now)

        self.assertEqual(
            target,
            datetime.datetime(2026, 7, 27, 9, tzinfo=datetime.UTC),
        )

    async def test_failed_delivery_stays_queued_then_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/reminders.db"
            connection = reminders_database(path)
            connection.execute(
                "INSERT INTO reminders (id, chat_id, user_id, title, target_time) "
                "VALUES (1, -1001, 9, 'ship it', 1)"
            )
            connection.close()

            bot = AsyncMock()
            bot.send_message.side_effect = TimedOut("temporary network failure")
            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            await run_worker(connection, bot)

            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            row = connection.execute(
                "SELECT attempt_count, claim_time, last_error FROM reminders WHERE id = 1"
            ).fetchone()
            self.assertEqual(row[0], 1)
            self.assertIsNotNone(row[1])
            self.assertIn("temporary network failure", row[2])

            connection.close()
            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            await run_worker(connection, bot)
            self.assertEqual(bot.send_message.await_count, 1)

            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            connection.execute("UPDATE reminders SET claim_time = 0 WHERE id = 1")
            connection.close()
            bot.send_message.side_effect = None
            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            await run_worker(connection, bot)

            connection = libsql.connect(path)
            remaining = connection.execute("SELECT COUNT(*) FROM reminders").fetchone()[
                0
            ]
            connection.close()

        self.assertEqual(remaining, 0)
        self.assertEqual(bot.send_message.await_count, 2)

    async def test_delivery_uses_stable_user_id_mention(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/reminders.db"
            connection = reminders_database(path)
            connection.execute(
                "INSERT INTO reminders (id, chat_id, user_id, title, target_time) "
                "VALUES (1, -1001, 9, 'ship it', 1)"
            )
            connection.close()

            bot = AsyncMock()
            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            await run_worker(connection, bot)

        text = bot.send_message.await_args.args[1]
        self.assertIn('href="tg://user?id=9"', text)
        self.assertNotIn("@", text)

    async def test_chat_migration_updates_other_pending_reminders(self):
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/reminders.db"
            connection = reminders_database(path)
            connection.executemany(
                "INSERT INTO reminders (id, chat_id, user_id, title, target_time) "
                "VALUES (?, -1001, 9, ?, ?)",
                [(1, "due", 1), (2, "future", now + 3600)],
            )
            connection.close()

            bot = AsyncMock()
            bot.send_message.side_effect = [ChatMigrated(-2002), None]
            connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
            await run_worker(connection, bot)

            connection = libsql.connect(path)
            remaining = connection.execute(
                "SELECT id, chat_id FROM reminders"
            ).fetchall()
            connection.close()

        self.assertEqual(remaining, [(2, -2002)])
        self.assertEqual(bot.send_message.await_count, 2)


if __name__ == "__main__":
    unittest.main()
