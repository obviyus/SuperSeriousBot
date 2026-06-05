import asyncio
from typing import Any

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

import commands
from commands.runtime import ensure_command_available
from config.options import config
from utils.decorators import command
from utils.messages import get_message

KIE_API_URL = "https://api.kie.ai/api/v1"
KIE_CALLBACK_URL = "https://localhost/kie-callback"
SONG_PROMPT_CHAR_LIMIT = 200
LYRICS_POLL_ATTEMPTS = 36
MUSIC_POLL_ATTEMPTS = 96
POLL_INTERVAL_SECONDS = 5
SONG_STYLE = (
    "bright dance-pop, playful, catchy, big chorus, clean vocal, polished banger"
)
SONG_NEGATIVE_TAGS = "rap, spoken word, mumble rap, long dense verses"
SONG_MODEL = "V5"

type JsonObject = dict[str, Any]


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
    if len(user_prompt) > SONG_PROMPT_CHAR_LIMIT:
        await message.reply_text(
            f"Please keep your song prompt under {SONG_PROMPT_CHAR_LIMIT} characters."
        )
        return

    progress = await message.reply_text("Writing banger lyrics...")

    try:
        async with aiohttp.ClientSession() as session:
            lyrics_task_id = await create_task(
                session,
                "/lyrics",
                {"prompt": user_prompt, "callBackUrl": KIE_CALLBACK_URL},
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

            await progress.edit_text("Turning lyrics into a song...")
            music_task_id = await create_task(
                session,
                "/generate",
                {
                    "prompt": lyrics,
                    "style": SONG_STYLE,
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
        for track in song_tracks(music_task)[:2]:
            await message.reply_audio(
                audio=audio_url(track),
                title=str(track.get("title") or title),
                caption=f"{track.get('title') or title}",
            )
    except RuntimeError as exc:
        await progress.edit_text(f"Song generation failed: {exc!s}")
