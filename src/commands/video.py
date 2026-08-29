from __future__ import annotations

import asyncio
import base64
import io
import json
import math

import httpx2
from PIL import Image, ImageOps
from telegram import Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

import commands
from commands.ai import OPENROUTER_BASE_URL, OPENROUTER_HEADERS
from commands.runtime import HandledCommandError, ensure_command_available
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
VIDEO_FRAME_SIZES = (
    ("1:1", (480, 480)),
    ("3:4", (480, 640)),
    ("9:16", (480, 854)),
    ("4:3", (640, 480)),
    ("16:9", (854, 480)),
    ("21:9", (1120, 480)),
)
POLL_INTERVAL_SECONDS = 5
POLL_ATTEMPTS = 180
VIDEO_JOB_LOCK = asyncio.Lock()
VIDEO_REJECTION_MESSAGES = {
    "InputImageSensitiveContentDetected.PrivacyInformation": (
        "That image was rejected because it appears to contain a real person."
    ),
    "authentication": "Video generation is temporarily unavailable.",
    "content_policy_violation": "The image or prompt was rejected by the video safety filter.",
    "image_content_policy_violation": "The image or prompt was rejected by the video safety filter.",
    "image_download_failed": "The source image could not be read by the video service.",
    "image_not_found": "The source image could not be read by the video service.",
    "image_too_large": "That image is too large for video generation.",
    "image_too_small": "That image is too small for video generation.",
    "invalid_image": "That image cannot be read for video generation.",
    "payment_required": "Video generation credits are unavailable.",
    "rate_limit_exceeded": "The video service is busy. Try again shortly.",
    "refusal": "The image or prompt was rejected by the video safety filter.",
    "string_too_long": "The video prompt is too long.",
    "unsupported_image_format": "That image format cannot be used for video.",
}


class OpenRouterVideoError(RuntimeError):
    def __init__(
        self,
        status: int,
        error_type: str | None,
        detail: str | None,
    ) -> None:
        diagnostic = f"OpenRouter video rejected status={status}"
        if error_type:
            diagnostic += f" type={error_type}"
        if detail:
            diagnostic += f" detail={detail}"
        super().__init__(diagnostic)
        reason = VIDEO_REJECTION_MESSAGES.get(
            error_type,
            "The video request was rejected before generation.",
        )
        self.user_message = f"{reason} No video job was created."


def safe_error_detail(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    detail = " ".join(value.split())
    if len(detail) > 300 or "data:" in detail.lower() or "base64" in detail.lower():
        return None
    return detail


def nested_provider_error_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    _, separator, body = value.partition(": ")
    if not separator:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    error = data.get("error") if isinstance(data, dict) else None
    error_type = error.get("code") if isinstance(error, dict) else None
    return error_type if isinstance(error_type, str) else None


async def video_rejection(response: httpx2.Response) -> OpenRouterVideoError:
    try:
        data = response.json()
    except ValueError:
        data = None

    error = data.get("error") if isinstance(data, dict) else None
    metadata = error.get("metadata") if isinstance(error, dict) else None
    error_message = error.get("message") if isinstance(error, dict) else None
    error_type = metadata.get("error_type") if isinstance(metadata, dict) else None
    if not isinstance(error_type, str):
        error_type = data.get("error_type") if isinstance(data, dict) else None
    if not isinstance(error_type, str):
        error_type = nested_provider_error_type(error_message)
    detail = safe_error_detail(error_message)
    return OpenRouterVideoError(response.status_code, error_type, detail)


def image_input(image_data: bytes) -> tuple[str, str]:
    with Image.open(io.BytesIO(image_data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
        source_ratio = image.width / image.height
        aspect_ratio, frame_size = min(
            VIDEO_FRAME_SIZES,
            key=lambda item: abs(math.log(source_ratio / (item[1][0] / item[1][1]))),
        )
        image.thumbnail(frame_size, Image.Resampling.LANCZOS)
        offset = (
            (frame_size[0] - image.width) // 2,
            (frame_size[1] - image.height) // 2,
        )
        frame = Image.new("RGB", frame_size, "black")
        frame.paste(image, offset, image)

    output = io.BytesIO()
    frame.save(output, format="JPEG", quality=92, subsampling=0, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode()
    return aspect_ratio, f"data:image/jpeg;base64,{encoded}"


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
    session: httpx2.AsyncClient,
    request: dict[str, object],
) -> str:
    response = await session.post(
        f"{OPENROUTER_BASE_URL}/videos",
        json=request,
    )
    if response.status_code >= 400:
        raise await video_rejection(response)
    response.raise_for_status()
    data = response.json()
    job_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(job_id, str):
        raise TypeError("OpenRouter did not return a video job ID.")
    return job_id


async def wait_for_video(
    session: httpx2.AsyncClient,
    job_id: str,
) -> None:
    for _ in range(POLL_ATTEMPTS):
        response = await session.get(f"{OPENROUTER_BASE_URL}/videos/{job_id}")
        response.raise_for_status()
        data = response.json()
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
    session: httpx2.AsyncClient,
    job_id: str,
) -> bytes:
    response = await session.get(f"{OPENROUTER_BASE_URL}/videos/{job_id}/content")
    response.raise_for_status()
    return response.content


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
    job_completed = False
    try:
        timeout = httpx2.Timeout(None, connect=30, read=120)
        headers = {
            "Authorization": f"Bearer {api_key}",
            **OPENROUTER_HEADERS,
        }
        async with (
            VIDEO_JOB_LOCK,
            httpx2.AsyncClient(
                headers=headers, timeout=timeout, follow_redirects=True
            ) as session,
        ):
            request = build_video_request(prompt, source_image)
            job_id = await submit_video(session, request)
            await wait_for_video(session, job_id)
            job_completed = True
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
    except OpenRouterVideoError as exc:
        await replace_status(status, message, exc.user_message)
        raise HandledCommandError(str(exc)) from exc
    except (
        httpx2.HTTPError,
        TelegramError,
        TimeoutError,
        RuntimeError,
        TypeError,
        ValueError,
        OSError,
    ) as exc:
        failure_message = (
            "The video finished, but delivery failed. Don't retry yet; "
            "that could create a duplicate charge."
            if job_completed
            else "Video generation failed. Please try again."
        )
        await replace_status(
            status,
            message,
            failure_message,
        )
        raise HandledCommandError("Video command failed") from exc
