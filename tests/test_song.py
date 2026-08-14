from __future__ import annotations

import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pydantic

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")

song_module = importlib.import_module("commands.song")


class SongTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_song_plan_joins_lyric_lines(self):
        output = song_module.SongPlanOutput(
            title="Online Fever",
            lyricsLines=[
                "[Verse 1]",
                "Screen light",
                "Midnight",
                "[Chorus]",
                "Online",
                "Heart shine",
            ],
            style="upbeat Urdu pop, bright synths, catchy hook",
        )
        with patch.object(
            song_module,
            "generate_object",
            AsyncMock(return_value=output),
        ) as generate_object:
            plan = await song_module.plan_song("spreadsheet party")

        self.assertEqual(plan.title, "Online Fever")
        self.assertEqual(
            plan.lyrics,
            "[Verse 1]\nScreen light\nMidnight\n[Chorus]\nOnline\nHeart shine",
        )
        self.assertEqual(plan.style, "upbeat Urdu pop, bright synths, catchy hook")
        self.assertEqual(
            generate_object.await_args.kwargs["extra_body"],
            {"provider": {"require_parameters": True}},
        )

    def test_song_plan_output_uses_portable_schema(self):
        schema = song_module.SongPlanOutput.model_json_schema()
        properties = schema["properties"]
        self.assertEqual(schema["required"], ["title", "lyricsLines", "style"])
        self.assertEqual(properties["title"]["type"], "string")
        self.assertEqual(
            properties["lyricsLines"],
            {"items": {"type": "string"}, "title": "Lyricslines", "type": "array"},
        )
        self.assertEqual(properties["style"]["type"], "string")

    def test_song_plan_output_rejects_non_string_lyric_lines(self):
        with self.assertRaises(pydantic.ValidationError):
            song_module.SongPlanOutput(
                title="Bad Lines",
                lyricsLines=["[Verse 1]", 7],
                style="bright pop",
            )

    def test_song_media_group_requires_two_audio_tracks(self):
        tracks = [
            {"audioUrl": "https://example.com/a.mp3", "title": "A"},
            {"audioUrl": "https://example.com/b.mp3"},
        ]

        media_group = song_module.song_media_group(tracks, "Fallback")

        self.assertEqual(len(media_group), 2)
        self.assertEqual(media_group[0].media, "https://example.com/a.mp3")
        self.assertEqual(media_group[0].title, "A")
        self.assertEqual(media_group[1].media, "https://example.com/b.mp3")
        self.assertEqual(media_group[1].title, "Fallback")

    async def test_song_sends_audio_urls_with_long_timeout(self):
        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

        class FakeMessage:
            def __init__(self) -> None:
                self.from_user = SimpleNamespace(id=123)
                self.media_kwargs: dict[str, object] | None = None
                self.media = None

            async def reply_text(self, text: str, **_kwargs: object) -> FakeMessage:
                return self

            async def edit_text(self, text: str, **_kwargs: object) -> None:
                return None

            async def delete(self) -> None:
                return None

            async def reply_media_group(self, media, **kwargs: object) -> None:
                self.media = media
                self.media_kwargs = kwargs

        message = FakeMessage()
        update = SimpleNamespace(effective_user=message.from_user)
        context = SimpleNamespace(args=["punjabi", "banger"])

        with (
            patch.object(song_module, "get_message", return_value=message),
            patch.object(song_module.config.API, "OPENROUTER_API_KEY", "test-key"),
            patch.object(
                song_module,
                "ensure_command_available",
                AsyncMock(return_value=True),
            ),
            patch.object(song_module, "ensure_quota", AsyncMock(return_value=True)),
            patch.object(
                song_module,
                "plan_song",
                AsyncMock(
                    return_value=song_module.SongPlan("Title", "lyrics", "style")
                ),
            ),
            patch.object(song_module, "create_task", AsyncMock(return_value="task-1")),
            patch.object(
                song_module,
                "poll_task",
                AsyncMock(
                    return_value={
                        "response": {
                            "sunoData": [
                                {
                                    "audioUrl": "https://cdn.example/a.mp3",
                                    "title": "A",
                                },
                                {"audioUrl": "https://cdn.example/b.mp3"},
                            ]
                        }
                    }
                ),
            ),
            patch.object(song_module.aiohttp, "ClientSession", FakeSession),
        ):
            await song_module.song(update, context)

        self.assertIsNotNone(message.media)
        self.assertEqual(message.media[0].media, "https://cdn.example/a.mp3")
        self.assertEqual(message.media[1].media, "https://cdn.example/b.mp3")
        self.assertEqual(
            message.media_kwargs,
            {
                "read_timeout": song_module.SONG_SEND_TIMEOUT_SECONDS,
                "write_timeout": song_module.SONG_SEND_TIMEOUT_SECONDS,
                "connect_timeout": 30,
            },
        )


if __name__ == "__main__":
    unittest.main()
