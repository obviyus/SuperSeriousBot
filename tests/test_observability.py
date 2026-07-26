from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import libsql

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

command_usage = importlib.import_module("command_usage")
db = importlib.import_module("config.db")
migrate = importlib.import_module("migrate")
runtime = importlib.import_module("commands.runtime")


class ConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return None


def command_stats_database(path: str):
    connection = libsql.connect(path, autocommit=True, _check_same_thread=False)
    connection.execute(
        """
        CREATE TABLE command_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    migration = migrate.load_migration(
        Path("migrations/20260726020000_command_observability.py")
    )
    migration.upgrade(connection)
    return connection


class ObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_event_records_input_outcome_and_debug_context(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = command_stats_database(f"{directory}/usage.db")
            wrapped = db.TursoConnection(connection)
            message = SimpleNamespace(
                from_user=SimpleNamespace(
                    id=7,
                    username="alice",
                    full_name="Alice",
                ),
                chat_id=-1001,
                message_id=42,
                text="/search most contrarian person",
            )
            error = RuntimeError("provider timed out")
            try:
                with patch.object(
                    runtime,
                    "get_db",
                    return_value=ConnectionContext(wrapped),
                ):
                    await runtime.record_command_event(
                        message,
                        "search",
                        "failed",
                        1234,
                        error,
                    )
                row = connection.execute(
                    """
                    SELECT command, user_id, chat_id, message_id, username,
                           input_text, status, duration_ms, error_type, error_message,
                           error_traceback
                    FROM command_stats
                    """
                ).fetchone()
            finally:
                await wrapped.close()

        self.assertEqual(
            row,
            (
                "search",
                7,
                -1001,
                42,
                "@alice",
                "most contrarian person",
                "failed",
                1234,
                "RuntimeError",
                "provider timed out",
                "RuntimeError: provider timed out\n",
            ),
        )

    async def test_operator_report_returns_prompts_metrics_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = command_stats_database(f"{directory}/usage.db")
            connection.executemany(
                """
                INSERT INTO command_stats (
                    command, user_id, username, input_text, status,
                    duration_ms, error_type, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "search",
                        7,
                        "@alice",
                        "who likes <gulab jamun> most?",
                        "completed",
                        800,
                        None,
                        None,
                    ),
                    (
                        "ask",
                        8,
                        "@bob",
                        "hello",
                        "failed",
                        1200,
                        "TimeoutError",
                        "request expired",
                    ),
                ],
            )
            try:
                report = command_usage.usage_report(
                    connection,
                    days=7,
                    command=None,
                    status=None,
                    limit=100,
                )
            finally:
                connection.close()

        self.assertEqual(
            report["summary"],
            {
                "total": 2,
                "completed": 1,
                "blocked": 0,
                "failed": 1,
                "average_duration_ms": 1000,
            },
        )
        self.assertEqual(
            report["by_command"],
            [{"command": "ask", "count": 1}, {"command": "search", "count": 1}],
        )
        events = report["events"]
        self.assertIsInstance(events, list)
        self.assertEqual(events[0]["error_type"], "TimeoutError")
        self.assertEqual(events[1]["input_text"], "who likes <gulab jamun> most?")


if __name__ == "__main__":
    unittest.main()
