import asyncio
import json
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
LYRICS_PROMPT_CHAR_LIMIT = 200
SONG_STYLE_CHAR_LIMIT = 1000
LYRICS_POLL_ATTEMPTS = 36
MUSIC_POLL_ATTEMPTS = 96
POLL_INTERVAL_SECONDS = 5
SONG_PLANNER_MODEL = "x-ai/grok-4.3"
SONG_NEGATIVE_TAGS = "rap, spoken word, mumble rap, long dense verses"
SONG_MODEL = "V5"

type JsonObject = dict[str, Any]


SONG_PLANNER_SYSTEM_PROMPT = f"""Turn a user's song idea into KIE Suno inputs.

Return JSON only:
{{"lyricsPrompt":"...","style":"..."}}

lyricsPrompt rules:
- {LYRICS_PROMPT_CHAR_LIMIT} characters max.
- Ask for fun, singable lyrics based on the user's idea.
- Prefer short sung lines, 4-7 syllables, simple words, clean AABB or ABAB rhymes.
- Include verse, pre-chorus or lift, chorus, and a repeatable hook.
- Avoid rap, spoken word, dense bars, artist names, and copyrighted song titles.

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


async def plan_song(session: aiohttp.ClientSession, user_prompt: str) -> tuple[str, str]:
    payload: JsonObject = {
        "model": SONG_PLANNER_MODEL,
        "messages": [
            {"role": "system", "content": SONG_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 320,
        "response_format": {"type": "json_object"},
    }
    async with session.post(
        OPENROUTER_API_URL,
        headers=openrouter_headers(openrouter_api_key()),
        json=payload,
    ) as response:
        response.raise_for_status()
        data = await response.json()

    content = first_message_content(data if isinstance(data, dict) else {})
    if not isinstance(content, str):
        raise RuntimeError("OpenRouter did not return a song plan.")

    try:
        plan = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter returned an invalid song plan.") from exc

    lyrics_prompt = plan.get("lyricsPrompt") if isinstance(plan, dict) else None
    style = plan.get("style") if isinstance(plan, dict) else None
    if not isinstance(lyrics_prompt, str) or not isinstance(style, str):
        raise RuntimeError("OpenRouter returned an incomplete song plan.")
    if not lyrics_prompt.strip() or not style.strip():
        raise RuntimeError("OpenRouter returned an empty song plan.")
    if len(lyrics_prompt) > LYRICS_PROMPT_CHAR_LIMIT:
        raise RuntimeError("OpenRouter returned a lyrics prompt that was too long.")
    if len(style) > SONG_STYLE_CHAR_LIMIT:
        raise RuntimeError("OpenRouter returned a style that was too long.")
    return lyrics_prompt.strip(), style.strip()


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


def first_lyrics(task: JsonObject) -> tuple[str, str]:
    response = task.get("response")
    variants = response.get("data") if isinstance(response, dict) else None
    if not isinstance(variants, list):
        raise RuntimeError("No lyrics were generated.")

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if variant.get("status") != "complete":
            continue
        lyrics = variant.get("text")
        title = variant.get("title")
        if isinstance(lyrics, str) and isinstance(title, str) and len(lyrics) <= 5000:
            return title[:80], lyrics

    raise RuntimeError("No usable lyrics were generated.")


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

    progress = await message.reply_text("Planning the song...")

    try:
        async with aiohttp.ClientSession() as session:
            lyrics_prompt, style = await plan_song(session, user_prompt)

            await progress.edit_text("Writing banger lyrics...")
            lyrics_task_id = await create_task(
                session,
                "/lyrics",
                {"prompt": lyrics_prompt, "callBackUrl": KIE_CALLBACK_URL},
            )
            lyrics_task = await poll_task(
                session,
                "/lyrics/record-info",
                lyrics_task_id,
                "SUCCESS",
                {
                    "CREATE_TASK_FAILED",
                    "GENERATE_LYRICS_FAILED",
                    "CALLBACK_EXCEPTION",
                    "SENSITIVE_WORD_ERROR",
                },
                LYRICS_POLL_ATTEMPTS,
            )
            title, lyrics = first_lyrics(lyrics_task)

            await progress.edit_text("Turning lyrics into songs...")
            music_task_id = await create_task(
                session,
                "/generate",
                {
                    "prompt": lyrics,
                    "style": style,
                    "title": title,
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
        await message.reply_media_group(song_media_group(song_tracks(music_task), title))
    except RuntimeError as exc:
        await progress.edit_text(f"Song generation failed: {exc!s}")
