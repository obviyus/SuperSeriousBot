from __future__ import annotations

import ast
import importlib
import io
import os
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import libsql
from telegram import MessageEntity

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

chat_memory = importlib.import_module("management.chat_memory")
commands_module = importlib.import_module("commands")
db = importlib.import_module("config.db")
ask_module = importlib.import_module("commands.ask")
animals_module = importlib.import_module("commands.animals")
define_module = importlib.import_module("commands.define")
gif_module = importlib.import_module("commands.gif")
habit_module = importlib.import_module("commands.habit")
meme_module = importlib.import_module("commands.meme")
model_module = importlib.import_module("commands.model")
song_module = importlib.import_module("commands.song")
transcribe_module = importlib.import_module("commands.transcribe")
weather_module = importlib.import_module("commands.weather")
send_markdown_or_plain = importlib.import_module(
    "utils.messages"
).send_markdown_or_plain
decorators = importlib.import_module("utils.decorators")

USER_REPLY_METHODS = {
    "edit_text",
    "reply_text",
    "send_message",
}
FORBIDDEN_USER_COPY = (
    "OPENROUTER_API_KEY",
    "WEATHERAPI_API_KEY",
    "WAQI_API_KEY",
    "OpenRouter request failed",
    "Giphy",
    "Klipy",
    "Unexpected response structure",
    "Unsupported response from Cobalt",
)


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


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=123)
        self.reply_to_message = None
        self.replies: list[str] = []
        self.animations: list[str] = []

    async def reply_text(self, text: str, **_kwargs):
        self.replies.append(text)

    async def reply_animation(self, animation: str, **_kwargs):
        self.animations.append(animation)


class FakeResponse:
    def __init__(self, data: object = None, status: int = 200) -> None:
        self.data = {"data": []} if data is None else data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self):
        return self.data


class FakeSession:
    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses) or [FakeResponse()]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def get(self, *_args, **_kwargs):
        return self.responses.pop(0)


class FailingSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def get(self, *_args, **_kwargs):
        import aiohttp

        raise aiohttp.ClientError("network unavailable")


class FakeCursorForOpen:
    description = ()
    lastrowid = None
    rowcount = -1

    def close(self):
        return None


class FakeSyncConnection:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.closed = False
        self.queries: list[str] = []

    def execute(self, sql: str):
        self.queries.append(sql)
        if self.failure:
            raise self.failure
        return FakeCursorForOpen()

    def close(self):
        self.closed = True


class CommandRegressionTests(unittest.IsolatedAsyncioTestCase):
    def test_registered_commands_have_user_facing_help_metadata(self):
        for command in commands_module.list_of_commands:
            meta = decorators.get_command_meta(command)
            self.assertTrue(meta.triggers)
            self.assertTrue(meta.usage)
            self.assertTrue(meta.example)
            self.assertTrue(meta.description)

    def test_default_ai_models_match_live_verified_models(self):
        self.assertEqual(model_module.DEFAULT_MODELS["ask"], "openrouter/x-ai/grok-4.3")
        self.assertEqual(
            model_module.DEFAULT_MODELS["edit"],
            "openrouter/google/gemini-3.1-flash-image-preview",
        )
        self.assertEqual(
            model_module.DEFAULT_MODELS["tldr"],
            "openrouter/google/gemini-3-flash-preview",
        )

    def test_shiba_uses_live_verified_dog_ceo_contract(self):
        url, extract_url = animals_module.ANIMAL_APIS["shiba"]

        self.assertEqual(url, "https://dog.ceo/api/breed/shiba/images/random")
        self.assertEqual(
            extract_url({"status": "success", "message": "https://example.com/shiba.jpg"}),
            "https://example.com/shiba.jpg",
        )

    def test_user_facing_copy_does_not_leak_provider_diagnostics(self):
        leaks = []
        for path in sorted(Path("src").rglob("*.py")):
            source_tree = ast.parse(path.read_text())
            for node in ast.walk(source_tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr not in USER_REPLY_METHODS:
                    continue
                text_parts = []
                for argument in (*node.args, *(keyword.value for keyword in node.keywords)):
                    for child in ast.walk(argument):
                        if isinstance(child, ast.Constant) and isinstance(child.value, str):
                            text_parts.append(child.value)
                user_text = "\n".join(text_parts)
                for forbidden in FORBIDDEN_USER_COPY:
                    if forbidden in user_text:
                        leaks.append(f"{path}:{node.lineno}: {forbidden}")
        self.assertEqual(leaks, [])

    async def test_habit_rejects_non_numeric_weekly_goal(self):
        message = FakeMessage()
        update = SimpleNamespace(effective_chat=SimpleNamespace(id=-1001))
        context = SimpleNamespace(args=["workout", "often"])

        with patch.object(habit_module, "get_message", return_value=message):
            await habit_module.habit(update, context)

        self.assertEqual(message.replies, ["Please enter a number between 1 and 7."])

    async def test_ask_missing_key_uses_user_facing_message(self):
        message = FakeMessage()
        update = SimpleNamespace(effective_user=message.from_user)
        context = SimpleNamespace(args=["hello"])

        with (
            patch.object(ask_module, "get_message", return_value=message),
            patch.object(ask_module.config.API, "OPENROUTER_API_KEY", ""),
            patch.object(
                ask_module,
                "ensure_command_available",
                AsyncMock(return_value=True),
            ),
        ):
            await ask_module.ask(update, context)

        self.assertEqual(message.replies, ["AI is not configured for this command."])

    async def test_song_missing_openrouter_key_uses_user_facing_message(self):
        message = FakeMessage()
        update = SimpleNamespace(effective_user=message.from_user)
        context = SimpleNamespace(args=["party", "anthem"])

        with (
            patch.object(song_module, "get_message", return_value=message),
            patch.object(song_module.config.API, "OPENROUTER_API_KEY", ""),
            patch.object(
                song_module,
                "ensure_command_available",
                AsyncMock(return_value=True),
            ),
        ):
            await song_module.song(update, context)

        self.assertEqual(message.replies, ["Song generation is not fully configured."])

    async def test_transcribe_missing_key_uses_user_facing_message(self):
        message = FakeMessage()
        message.reply_to_message = SimpleNamespace(
            voice=SimpleNamespace(file_id="voice-file", mime_type="audio/ogg"),
            audio=None,
            document=None,
        )
        update = SimpleNamespace(effective_user=message.from_user)
        context = SimpleNamespace(args=[])

        with (
            patch.object(transcribe_module, "get_message", return_value=message),
            patch.object(transcribe_module.config.API, "OPENROUTER_API_KEY", ""),
            patch.object(
                transcribe_module,
                "ensure_command_available",
                AsyncMock(return_value=True),
            ),
        ):
            await transcribe_module.transcribe(update, context)

        self.assertEqual(message.replies, ["Transcription is not configured."])

    async def test_weather_missing_keys_uses_user_facing_message(self):
        message = FakeMessage()
        context = SimpleNamespace(args=["Mumbai"])

        with (
            patch.object(weather_module, "get_message", return_value=message),
            patch.object(weather_module.config.API, "WEATHERAPI_API_KEY", ""),
            patch.object(weather_module.config.API, "WAQI_API_KEY", ""),
        ):
            await weather_module.weather(SimpleNamespace(), context)

        self.assertEqual(message.replies, ["Could not fetch weather data right now."])

    async def test_gif_handles_empty_api_data(self):
        message = FakeMessage()

        with (
            patch.object(gif_module, "get_message", return_value=message),
            patch.object(gif_module.config.API, "KLIPY_API_KEY", "klipy-key"),
            patch("aiohttp.ClientSession", return_value=FakeSession()),
        ):
            await gif_module.gif(SimpleNamespace(), SimpleNamespace())

        self.assertEqual(message.replies, ["Could not fetch a GIF right now."])
        self.assertEqual(message.animations, [])

    async def test_gif_uses_klipy_trending_response(self):
        message = FakeMessage()
        data = {
            "result": True,
            "data": {
                "data": [
                    {
                        "file": {
                            "md": {
                                "gif": {"url": "https://cdn.example.com/hype.gif"},
                            },
                        }
                    }
                ]
            },
        }

        with (
            patch.object(gif_module, "get_message", return_value=message),
            patch.object(gif_module.config.API, "KLIPY_API_KEY", "klipy-key"),
            patch("aiohttp.ClientSession", return_value=FakeSession(FakeResponse(data))),
        ):
            await gif_module.gif(SimpleNamespace(), SimpleNamespace())

        self.assertEqual(message.replies, [])
        self.assertEqual(message.animations, ["https://cdn.example.com/hype.gif"])

    async def test_define_handles_network_error(self):
        message = FakeMessage()
        context = SimpleNamespace(args=["posthumous"])

        with (
            patch.object(define_module, "get_message", return_value=message),
            patch("aiohttp.ClientSession", return_value=FailingSession()),
        ):
            await define_module.define(SimpleNamespace(), context)

        self.assertEqual(message.replies, ["Could not fetch a definition right now."])

    async def test_meme_handles_missing_url(self):
        message = FakeMessage()

        with (
            patch.object(meme_module, "get_message", return_value=message),
            patch("aiohttp.ClientSession", return_value=FakeSession(FakeResponse({}))),
        ):
            await meme_module.meme(SimpleNamespace(), SimpleNamespace())

        self.assertEqual(message.replies, ["Could not fetch a meme right now."])

    async def test_weather_handles_malformed_api_data(self):
        message = FakeMessage()
        context = SimpleNamespace(args=["Mumbai"])

        with (
            patch.object(weather_module, "get_message", return_value=message),
            patch.object(weather_module.config.API, "WEATHERAPI_API_KEY", "weather-key"),
            patch.object(weather_module.config.API, "WAQI_API_KEY", "waqi-key"),
            patch(
                "aiohttp.ClientSession",
                return_value=FakeSession(FakeResponse({"location": {}})),
            ),
        ):
            await weather_module.weather(SimpleNamespace(), context)

        self.assertEqual(message.replies, ["Could not fetch weather data right now."])

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

    async def test_turso_open_retries_hrana_closed_stream(self):
        failed = FakeSyncConnection(
            ValueError("Hrana: `http error: `connection closed before message completed``")
        )
        recovered = FakeSyncConnection()

        with (
            patch.object(db, "open_sync_connection", side_effect=[failed, recovered]),
            patch.object(db.asyncio, "sleep", AsyncMock()) as sleep,
        ):
            conn = await db._open_connection()

        self.assertTrue(failed.closed)
        self.assertEqual(failed.queries, ["PRAGMA foreign_keys = ON;"])
        self.assertEqual(recovered.queries, ["PRAGMA foreign_keys = ON;"])
        sleep.assert_awaited_once_with(db.DB_OPEN_RETRY_DELAY_SECONDS)
        await conn.close()
        self.assertTrue(recovered.closed)

    async def test_turso_open_does_not_retry_unrelated_errors(self):
        failed = FakeSyncConnection(ValueError("syntax error"))

        with (
            patch.object(db, "open_sync_connection", return_value=failed) as connect,
            patch.object(db.asyncio, "sleep", AsyncMock()) as sleep,
        ):
            with self.assertRaisesRegex(ValueError, "syntax error"):
                await db._open_connection()

        self.assertEqual(connect.call_count, 1)
        self.assertTrue(failed.closed)
        sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
