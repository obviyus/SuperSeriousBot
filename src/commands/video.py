from __future__ import annotations

import asyncio
import base64
import io
import math

import aiohttp
from PIL import Image
from telegram import Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

import commands
from commands.ai import OPENROUTER_BASE_URL, OPENROUTER_HEADERS
from commands.runtime import ensure_command_available
from config.logger import logger
from config.options import config
from utils.command_limits import ensure_quota
from utils.decorators import command
from utils.media import get_message_image_bytes
from utils.messages import get_message

VIDEO_MODEL = "bytedance/seedance-2.0-mini"
VIDEO_DURATION_SECONDS = 5
VIDEO_RESOLUTION = "480p"
TEXT_VIDEO_ASPECT_RATIO = "16:9"
SUPPORTED_ASPECT_RATIOS = (
    ("1:1", 1.0),
    ("3:4", 3 / 4),
    ("9:16", 9 / 16),
    ("4:3", 4 / 3),
    ("16:9", 16 / 9),
    ("21:9", 21 / 9),
    ("9:21", 9 / 21),
)
POLL_INTERVAL_SECONDS = 5
POLL_ATTEMPTS = 180
VIDEO_JOB_LOCK = asyncio.Lock()


def image_input(image_data: bytes) -> tuple[str, str]:
    with Image.open(io.BytesIO(image_data)) as image:
        source_ratio = image.width / image.height
        mime_type = Image.MIME.get(image.format or "")

    if not mime_type:
        raise ValueError("Unsupported source image format.")
    aspect_ratio = min(
        SUPPORTED_ASPECT_RATIOS,
        key=lambda item: abs(math.log(source_ratio / item[1])),
    )[0]
    encoded = base64.b64encode(image_data).decode()
    return aspect_ratio, f"data:{mime_type};base64,{encoded}"


def build_video_request(
    prompt: str,
    source_image: tuple[bytes, str | None] | None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "duration": VIDEO_DURATION_SECONDS,
        "resolution": VIDEO_RESOLUTION,
        "aspect_ratio": TEXT_VIDEO_ASPECT_RATIO,
        "generate_audio": True,
    }
    if source_image:
        aspect_ratio, image_url = image_input(source_image[0])
        request["aspect_ratio"] = aspect_ratio
        request["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": image_url},
                "frame_type": "first_frame",
            }
        ]
    return request


async def submit_video(
    session: aiohttp.ClientSession,
    request: dict[str, object],
) -> str:
    async with session.post(
        f"{OPENROUTER_BASE_URL}/videos",
        json=request,
    ) as response:
        response.raise_for_status()
        data = await response.json()
    job_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(job_id, str):
        raise TypeError("OpenRouter did not return a video job ID.")
    return job_id


async def wait_for_video(
    session: aiohttp.ClientSession,
    job_id: str,
) -> None:
    for _ in range(POLL_ATTEMPTS):
        async with session.get(f"{OPENROUTER_BASE_URL}/videos/{job_id}") as response:
            response.raise_for_status()
            data = await response.json()
        status = data.get("status") if isinstance(data, dict) else None
        if status == "completed":
            logger.info(
                "OpenRouter video completed job_id=%s usage=%s",
                job_id,
                data.get("usage"),
            )
            return
        if status == "failed":
            raise RuntimeError(f"OpenRouter video failed: {data.get('error')}")
        if status not in ("pending", "in_progress"):
            raise TypeError("OpenRouter returned an invalid video job status.")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("OpenRouter video generation timed out.")


async def download_video(
    session: aiohttp.ClientSession,
    job_id: str,
) -> bytes:
    async with session.get(
        f"{OPENROUTER_BASE_URL}/videos/{job_id}/content"
    ) as response:
        response.raise_for_status()
        return await response.read()


async def replace_status(status: Message | None, message: Message, text: str) -> None:
    if status:
        try:
            await status.edit_text(text)
            return
        except BadRequest:
            pass
    await message.reply_text(text)


@command(
    triggers=["video"],
    usage="/video [prompt]",
    api_key="OPENROUTER_API_KEY",
    example="/video A corgi surfs a glassy wave. Audio: ocean surf, no music.",
    description="Generate a five-second video with audio. Reply to an image or static sticker to animate it.",
)
async def video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return
    if not await ensure_command_available(message, message.from_user.id, "video"):
        return
    if not context.args:
        await commands.usage_string(message, video)
        return
    if not await ensure_quota(message, message.from_user.id, "video"):
        return

    api_key = config.API.OPENROUTER_API_KEY
    if not api_key:
        await message.reply_text("Video generation is not configured.")
        return

    prompt = " ".join(context.args)
    source_image = None
    if message.reply_to_message:
        try:
            source_image = await get_message_image_bytes(
                message.reply_to_message,
                context.bot,
                allow_document=True,
            )
        except ValueError as exc:
            await message.reply_text(str(exc))
            return

    status = await message.reply_text(
        "Queued for a five-second video. Generation usually takes about two minutes."
    )
    try:
        timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=120)
        headers = {
            "Authorization": f"Bearer {api_key}",
            **OPENROUTER_HEADERS,
        }
        async with (
            VIDEO_JOB_LOCK,
            aiohttp.ClientSession(headers=headers, timeout=timeout) as session,
        ):
            request = build_video_request(prompt, source_image)
            job_id = await submit_video(session, request)
            await wait_for_video(session, job_id)
            video_bytes = await download_video(session, job_id)

        buffer = io.BytesIO(video_bytes)
        buffer.name = "seedance.mp4"
        user_mention = (
            f"@{update.effective_user.username}"
            if update.effective_user.username
            else f"User {update.effective_user.id}"
        )
        caption_prompt = prompt if len(prompt) <= 850 else f"{prompt[:847]}..."
        await message.reply_video(
            buffer,
            caption=f"🎬 Requested by {user_mention}\n📝 Prompt: {caption_prompt}",
            supports_streaming=True,
            read_timeout=120,
            write_timeout=120,
        )
        if status:
            try:
                await status.delete()
            except BadRequest:
                pass
    except (
        aiohttp.ClientError,
        TelegramError,
        TimeoutError,
        RuntimeError,
        TypeError,
        ValueError,
        OSError,
    ):
        logger.exception("Video command failed")
        await replace_status(
            status,
            message,
            "Video generation failed. Please try again.",
        )
