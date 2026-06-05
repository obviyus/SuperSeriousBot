import asyncio
import json
from dataclasses import dataclass
from typing import Any

import aiohttp
from telegram import InputMediaAudio, Update
from telegram.ext import ContextTypes

import commands
from commands.ai import (
    OPENROUTER_API_URL,
    first_message_content,
    openrouter_api_key,
    openrouter_headers,
)
from commands.runtime import ensure_command_available
from config.options import config
from utils.decorators import command
from utils.messages import get_message

KIE_API_URL = "https://api.kie.ai/api/v1"
KIE_CALLBACK_URL = "https://localhost/kie-callback"
SONG_LYRICS_CHAR_LIMIT = 5000
SONG_STYLE_CHAR_LIMIT = 1000
SONG_TITLE_CHAR_LIMIT = 80
MUSIC_POLL_ATTEMPTS = 96
POLL_INTERVAL_SECONDS = 5
SONG_PLANNER_MODEL = "x-ai/grok-4.3"
SONG_NEGATIVE_TAGS = "rap, spoken word, mumble rap, long dense verses"
SONG_MODEL = "V5"

type JsonObject = dict[str, Any]


@dataclass(frozen=True)
class SongPlan:
    title: str
    lyrics: str
    style: str


SONG_PLANNER_SYSTEM_PROMPT = f"""Write finished custom song inputs for KIE Suno.

Return JSON only:
{{"title":"...","lyricsLines":["..."],"style":"..."}}

lyrics rules:
- {SONG_LYRICS_CHAR_LIMIT} characters max.
- Write the final lyrics directly, not instructions for another model.
- Put every section tag or sung lyric line in its own lyricsLines item.
- Use Suno custom lyric section tags where useful, like [Verse 1], [Pre-Chorus], [Chorus], [Bridge].
- Verses default to short sung lines, about 4-7 syllables, simple words, clean AABB or ABAB rhymes.
- Include verse, pre-chorus or lift, chorus, and a repeatable hook.
- Avoid rap, spoken word, dense bars, artist names, and copyrighted song titles.
- Preserve requested language. If the user asks for Urdu, write Urdu lyrics in Urdu script unless they ask for Roman Urdu.
- Do not translate a requested non-English song into English.
- Keep section tags in English even when lyric lines use another language.

title rules:
- {SONG_TITLE_CHAR_LIMIT} characters max.
- Match the lyric language when natural.

style rules:
- {SONG_STYLE_CHAR_LIMIT} characters max.
- Concise Suno style tags and vocal/production direction.
- Make it catchy and high-energy unless the user asks otherwise.
- Avoid artist names and copyrighted song titles."""


def kie_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.API.KIE_API_KEY}",
        "Content-Type": "application/json",
    }


async def kie_json(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    **kwargs: object,
) -> JsonObject:
    async with session.request(
        method,
        f"{KIE_API_URL}{path}",
        headers=kie_headers(),
        **kwargs,
    ) as response:
        data = await response.json()
        if response.status != 200 or data.get("code") != 200:
            raise RuntimeError(str(data.get("msg") or "KIE request failed"))
        return data


def song_plan_payload(user_prompt: str) -> JsonObject:
    return {
        "model": SONG_PLANNER_MODEL,
        "messages": [
            {"role": "system", "content": SONG_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1800,
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "song_plan",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "maxLength": SONG_TITLE_CHAR_LIMIT,
                        },
                        "lyricsLines": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 120},
                            "minItems": 1,
                            "maxItems": 80,
                        },
                        "style": {
                            "type": "string",
                            "maxLength": SONG_STYLE_CHAR_LIMIT,
                        },
                    },
                    "required": ["title", "lyricsLines", "style"],
                    "additionalProperties": False,
                },
            },
        },
    }


def parse_song_plan_response(data: object) -> SongPlan:
    response: JsonObject = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str):
                response[key] = value
    content = first_message_content(response)
    if not isinstance(content, str):
        raise RuntimeError("OpenRouter did not return a song plan.")

    try:
        plan = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter returned an invalid song plan.") from exc

    title = plan.get("title") if isinstance(plan, dict) else None
    lyrics_lines = plan.get("lyricsLines") if isinstance(plan, dict) else None
    style = plan.get("style") if isinstance(plan, dict) else None
    if (
        not isinstance(title, str)
        or not isinstance(lyrics_lines, list)
        or not isinstance(style, str)
    ):
        raise RuntimeError("OpenRouter returned an incomplete song plan.")
    if not all(isinstance(line, str) for line in lyrics_lines):
        raise RuntimeError("OpenRouter returned invalid lyrics.")

    lyrics = "\n".join(line.strip() for line in lyrics_lines if line.strip())
    if not title.strip() or not lyrics or not style.strip():
        raise RuntimeError("OpenRouter returned an empty song plan.")
    if len(title) > SONG_TITLE_CHAR_LIMIT:
        raise RuntimeError("OpenRouter returned a title that was too long.")
    if len(lyrics) > SONG_LYRICS_CHAR_LIMIT:
        raise RuntimeError("OpenRouter returned lyrics that were too long.")
    if len(style) > SONG_STYLE_CHAR_LIMIT:
        raise RuntimeError("OpenRouter returned a style that was too long.")
    return SongPlan(title.strip(), lyrics.strip(), style.strip())


async def plan_song(session: aiohttp.ClientSession, user_prompt: str) -> SongPlan:
    payload = song_plan_payload(user_prompt)
    async with session.post(
        OPENROUTER_API_URL,
        headers=openrouter_headers(openrouter_api_key()),
        json=payload,
    ) as response:
        response.raise_for_status()
        data = await response.json()

    return parse_song_plan_response(data)


async def create_task(
    session: aiohttp.ClientSession,
    path: str,
    payload: JsonObject,
) -> str:
    data = await kie_json(session, "POST", path, json=payload)
    task_id = data.get("data", {}).get("taskId")
    if not isinstance(task_id, str):
        raise RuntimeError("KIE did not return a task.")
    return task_id


async def poll_task(
    session: aiohttp.ClientSession,
    path: str,
    task_id: str,
    final_status: str,
    failed_statuses: set[str],
    attempts: int,
) -> JsonObject:
    for _ in range(attempts):
        data = await kie_json(session, "GET", path, params={"taskId": task_id})
        task = data.get("data")
        if not isinstance(task, dict):
            raise RuntimeError("KIE did not return task details.")
        status = task.get("status")
        if status == final_status:
            return task
        if status in failed_statuses:
            message = task.get("errorMessage")
            raise RuntimeError(str(message or "KIE generation failed"))
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError("KIE generation timed out.")


def song_tracks(task: JsonObject) -> list[JsonObject]:
    response = task.get("response")
    suno_data = response.get("sunoData") if isinstance(response, dict) else None
    if not isinstance(suno_data, list):
        raise RuntimeError("No song files were generated.")
    tracks = [track for track in suno_data if isinstance(track, dict)]
    if not tracks:
        raise RuntimeError("No song files were generated.")
    return tracks


def audio_url(track: JsonObject) -> str:
    url = track.get("audioUrl")
    if not isinstance(url, str) or not url:
        raise RuntimeError("Generated song is missing audio.")
    return url


def song_media_group(tracks: list[JsonObject], fallback_title: str) -> list[InputMediaAudio]:
    selected_tracks = tracks[:2]
    if len(selected_tracks) != 2:
        raise RuntimeError("KIE generated fewer than two songs.")
    return [
        InputMediaAudio(
            media=audio_url(track),
            title=str(track.get("title") or fallback_title),
            caption=str(track.get("title") or fallback_title),
        )
        for track in selected_tracks
    ]


@command(
    triggers=["song"],
    usage="/song <prompt>",
    example="/song everyone at the party is secretly a spreadsheet",
    description="Generate a song from a short prompt.",
    api_key="KIE_API_KEY",
)
async def song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return

    if not await ensure_command_available(message, message.from_user.id, "song"):
        return

    user_prompt = " ".join(context.args).strip() if context.args else ""
    if not user_prompt:
        await commands.usage_string(message, song)
        return

    if not config.API.OPENROUTER_API_KEY:
        await message.reply_text("OPENROUTER_API_KEY is required to use this command.")
        return

    progress = await message.reply_text("Writing banger lyrics...")

    try:
        async with aiohttp.ClientSession() as session:
            song_plan = await plan_song(session, user_prompt)

            await progress.edit_text("Turning lyrics into songs...")
            music_task_id = await create_task(
                session,
                "/generate",
                {
                    "prompt": song_plan.lyrics,
                    "style": song_plan.style,
                    "title": song_plan.title,
                    "customMode": True,
                    "instrumental": False,
                    "model": SONG_MODEL,
                    "callBackUrl": KIE_CALLBACK_URL,
                    "negativeTags": SONG_NEGATIVE_TAGS,
                },
            )
            music_task = await poll_task(
                session,
                "/generate/record-info",
                music_task_id,
                "SUCCESS",
                {
                    "CREATE_TASK_FAILED",
                    "GENERATE_AUDIO_FAILED",
                    "CALLBACK_EXCEPTION",
                    "SENSITIVE_WORD_ERROR",
                },
                MUSIC_POLL_ATTEMPTS,
            )

        await progress.delete()
        await message.reply_media_group(
            song_media_group(song_tracks(music_task), song_plan.title)
        )
    except RuntimeError as exc:
        await progress.edit_text(f"Song generation failed: {exc!s}")
