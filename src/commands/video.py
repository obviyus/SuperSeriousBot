from __future__ import annotations

import asyncio
import io
import json
import mimetypes
import secrets
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from PIL import Image, ImageOps
from telegram import Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

import commands
from commands.runtime import ensure_command_available
from config.logger import logger
from config.options import config
from utils.command_limits import ensure_quota
from utils.decorators import command
from utils.media import get_message_image_bytes
from utils.messages import get_message

POLL_INTERVAL_SECONDS = 5
POLL_ATTEMPTS = 180
VIDEO_SIZE = (864, 480)
WORKFLOW_PATH = Path(__file__).with_name("minimax_h3_workflow.json")
VIDEO_JOB_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class ComfyFile:
    filename: str
    subfolder: str
    file_type: str


def string_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


def build_workflow(
    prompt: str,
    seed: int,
    first_frame: str | None = None,
) -> dict:
    workflow = json.loads(WORKFLOW_PATH.read_text())
    workflow["9"]["inputs"]["prompt"] = prompt
    workflow["9"]["inputs"]["width"] = VIDEO_SIZE[0]
    workflow["9"]["inputs"]["height"] = VIDEO_SIZE[1]
    workflow["13"]["inputs"]["noise_seed"] = seed
    if first_frame:
        workflow["20"] = {
            "class_type": "LoadImage",
            "inputs": {"image": first_frame},
        }
        workflow["9"]["inputs"]["first_frame"] = ["20", 0]
    return workflow


def letterbox_first_frame(image_data: bytes) -> bytes:
    with Image.open(io.BytesIO(image_data)) as image:
        source = ImageOps.contain(
            ImageOps.exif_transpose(image).convert("RGBA"),
            VIDEO_SIZE,
            Image.Resampling.LANCZOS,
        )

    frame = Image.new("RGB", VIDEO_SIZE)
    offset = (
        (VIDEO_SIZE[0] - source.width) // 2,
        (VIDEO_SIZE[1] - source.height) // 2,
    )
    frame.paste(source, offset, source)
    output = io.BytesIO()
    frame.save(output, format="PNG")
    return output.getvalue()


async def upload_image(
    session: aiohttp.ClientSession,
    base_url: str,
    image: bytes,
    mime_type: str | None,
) -> str:
    suffix = mimetypes.guess_extension(mime_type or "image/jpeg") or ".jpg"
    filename = f"superseriousbot-{secrets.token_hex(8)}{suffix}"
    form = aiohttp.FormData()
    form.add_field(
        "image",
        image,
        filename=filename,
        content_type=mime_type or "image/jpeg",
    )
    form.add_field("overwrite", "false")
    async with session.post(f"{base_url}/upload/image", data=form) as response:
        response.raise_for_status()
        data = await response.json()
    uploaded_name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(uploaded_name, str):
        raise TypeError("H3 did not accept the source image.")
    return uploaded_name


async def queue_video(
    session: aiohttp.ClientSession,
    base_url: str,
    workflow: dict,
) -> str:
    async with session.post(
        f"{base_url}/prompt",
        json={"prompt": workflow},
    ) as response:
        response.raise_for_status()
        data = await response.json()
    prompt_id = data.get("prompt_id") if isinstance(data, dict) else None
    if not isinstance(prompt_id, str):
        raise TypeError("H3 did not queue the video.")
    return prompt_id


def completed_video(history: object, prompt_id: str) -> ComfyFile | None:
    history_data = string_dict(history)
    if history_data is None:
        raise RuntimeError("H3 returned invalid job history.")
    result_value = history_data.get(prompt_id)
    if result_value is None:
        return None
    result = string_dict(result_value)
    if result is None:
        raise RuntimeError("H3 returned invalid job details.")

    status = string_dict(result.get("status"))
    if status is not None and status.get("status_str") == "error":
        raise RuntimeError("H3 failed to generate the video.")

    outputs = string_dict(result.get("outputs"))
    if outputs is not None:
        for output_value in outputs.values():
            output = string_dict(output_value)
            if output is None:
                continue
            for field in ("videos", "images"):
                files = output.get(field)
                if not isinstance(files, list):
                    continue
                for file_value in files:
                    file = string_dict(file_value)
                    if file is None:
                        continue
                    filename = file.get("filename")
                    subfolder = file.get("subfolder", "")
                    file_type = file.get("type", "output")
                    if (
                        isinstance(filename, str)
                        and filename.endswith(".mp4")
                        and isinstance(subfolder, str)
                        and isinstance(file_type, str)
                    ):
                        return ComfyFile(filename, subfolder, file_type)

    if status is not None and status.get("completed") is True:
        raise RuntimeError("H3 completed without a video.")
    return None


async def wait_for_video(
    session: aiohttp.ClientSession,
    base_url: str,
    prompt_id: str,
) -> ComfyFile:
    for _ in range(POLL_ATTEMPTS):
        async with session.get(f"{base_url}/history/{prompt_id}") as response:
            response.raise_for_status()
            output = completed_video(await response.json(), prompt_id)
        if output:
            return output
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("H3 video generation timed out.")


async def download_video(
    session: aiohttp.ClientSession,
    base_url: str,
    output: ComfyFile,
) -> bytes:
    async with session.get(
        f"{base_url}/view",
        params={
            "filename": output.filename,
            "subfolder": output.subfolder,
            "type": output.file_type,
        },
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
    api_key="MINIMAX_H3_URL",
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

    base_url = config.API.MINIMAX_H3_URL.rstrip("/")
    if not base_url:
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
        "Generating a five-second video. This usually takes about four minutes."
    )
    try:
        timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=120)
        async with (
            VIDEO_JOB_LOCK,
            aiohttp.ClientSession(timeout=timeout) as session,
        ):
            first_frame = None
            if source_image:
                first_frame = await upload_image(
                    session,
                    base_url,
                    letterbox_first_frame(source_image[0]),
                    "image/png",
                )
            workflow = build_workflow(
                prompt,
                secrets.randbits(63),
                first_frame,
            )
            prompt_id = await queue_video(session, base_url, workflow)
            output = await wait_for_video(session, base_url, prompt_id)
            video_bytes = await download_video(session, base_url, output)

        buffer = io.BytesIO(video_bytes)
        buffer.name = output.filename
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
    ):
        logger.exception("Video command failed")
        await replace_status(
            status,
            message,
            "Video generation failed. Please try again.",
        )
