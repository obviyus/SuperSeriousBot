from __future__ import annotations

import importlib
import json
import os
import unittest

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")

song_module = importlib.import_module("commands.song")


def openrouter_response(content: object) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content),
                },
            },
        ],
    }


def song_plan_schema() -> dict[str, object]:
    payload = song_module.song_plan_payload("spreadsheet party")
    response_format = payload["response_format"]
    response_format = string_dict(response_format)
    json_schema = response_format["json_schema"]
    json_schema = string_dict(json_schema)
    schema = json_schema["schema"]
    return string_dict(schema)


def string_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return {key: item for key, item in value.items() if isinstance(key, str)}


class SongTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_song_plan_joins_lyric_lines(self):
        plan = song_module.parse_song_plan_response(
            openrouter_response(
                {
                    "title": "Online Fever",
                    "lyricsLines": [
                        "[Verse 1]",
                        "Screen light",
                        "Midnight",
                        "[Chorus]",
                        "Online",
                        "Heart shine",
                    ],
                    "style": "upbeat Urdu pop, bright synths, catchy hook",
                }
            )
        )

        self.assertEqual(plan.title, "Online Fever")
        self.assertEqual(
            plan.lyrics,
            "[Verse 1]\nScreen light\nMidnight\n[Chorus]\nOnline\nHeart shine",
        )
        self.assertEqual(plan.style, "upbeat Urdu pop, bright synths, catchy hook")

    async def test_song_plan_payload_requests_line_array_schema(self):
        payload = song_module.song_plan_payload("spreadsheet party")
        schema = song_plan_schema()
        properties = schema["properties"]
        properties = string_dict(properties)
        lyrics_lines = properties["lyricsLines"]
        lyrics_lines = string_dict(lyrics_lines)
        items = lyrics_lines["items"]
        items = string_dict(items)

        self.assertEqual(payload["max_tokens"], 1800)
        self.assertEqual(schema["required"], ["title", "lyricsLines", "style"])
        self.assertEqual(lyrics_lines["type"], "array")
        self.assertEqual(items["maxLength"], 120)

    async def test_parse_song_plan_rejects_non_string_lyric_lines(self):
        response = openrouter_response(
            {
                "title": "Bad Lines",
                "lyricsLines": ["[Verse 1]", 7],
                "style": "bright pop",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "invalid lyrics"):
            song_module.parse_song_plan_response(response)

    def test_song_media_group_requires_two_audio_tracks(self):
        tracks = [
            {"audioUrl": "https://example.com/a.mp3", "title": "A"},
            {"audioUrl": "https://example.com/b.mp3"},
        ]

        media_group = song_module.song_media_group(tracks, "Fallback")

        self.assertEqual(len(media_group), 2)
        self.assertEqual(media_group[0].title, "A")
        self.assertEqual(media_group[1].title, "Fallback")


if __name__ == "__main__":
    unittest.main()
