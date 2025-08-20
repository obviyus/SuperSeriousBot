import io

import aiohttp
from telegram import InputFile, InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import utils
from config.logger import logger
from config.options import config
from utils.decorators import description, example, triggers, usage

MAX_MEDIA_COUNT = 10
MAX_DOWNLOAD_SIZE = 47 * (1 << 20)  # ~47 MB cap to stay under Telegram limits


def _is_image(filename_or_url: str) -> bool:
    name = filename_or_url.lower()
    return name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def _is_video(filename_or_url: str) -> bool:
    name = filename_or_url.lower()
    return name.endswith((".mp4", ".mov", ".webm", ".mkv", ".avi"))


async def _download_to_memory(
    url: str,
) -> tuple[io.BytesIO, str | None, int | None]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Download failed: {resp.status} {text[:120]}")

            content_length_header = resp.headers.get("Content-Length")
            expected_size = (
                int(content_length_header)
                if content_length_header and content_length_header.isdigit()
                else None
            )
            if expected_size and expected_size > MAX_DOWNLOAD_SIZE:
                raise RuntimeError("File too large to download in memory.")

            buffer = io.BytesIO()
            downloaded = 0
            async for chunk in resp.content.iter_chunked(262144):  # 256 KiB
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_SIZE:
                    raise RuntimeError("File too large to download in memory.")
                buffer.write(chunk)

            buffer.seek(0)
            return buffer, resp.headers.get("Content-Type"), expected_size


async def _fetch_and_send(message: Message, url: str, filename: str | None) -> None:
    try:
        buffer, content_type, _ = await _download_to_memory(url)
        safe_name = filename or "file"
        file = InputFile(buffer, filename=safe_name)
        target_name = safe_name.lower()

        if _is_image(target_name) or (
            content_type and content_type.startswith("image/")
        ):
            await message.reply_photo(photo=file)
            return
        if _is_video(target_name) or (
            content_type and content_type.startswith("video/")
        ):
            await message.reply_video(video=file)
            return

        await message.reply_document(document=file)
    except BadRequest as e:
        logger.error(f"Failed to send media: {e}")
        await message.reply_text("Media unavailable or too large.")
    except Exception as e:
        logger.error(f"Failed to download media: {e}")
        await message.reply_text("Failed to download media.")


async def _send_picker(message: Message, picker_items: list[dict]) -> None:
    if not picker_items:
        await message.reply_text("No media found.")
        return

    media_group = []
    for item in picker_items[:MAX_MEDIA_COUNT]:
        url = item.get("url")
        typ = (item.get("type") or "").lower()
        if not url:
            continue
        if typ == "photo" or _is_image(url):
            media_group.append(InputMediaPhoto(url))
        else:
            media_group.append(InputMediaVideo(url))

    if not media_group:
        await message.reply_text("No media found.")
        return

    try:
        await message.reply_media_group(media_group)
    except BadRequest as e:
        logger.error(f"Failed to send media group: {e}")
        await message.reply_text("Media unavailable or too large.")


async def _cobalt_request(cobalt_base_url: str, target_url: str) -> dict:
    endpoint = cobalt_base_url.rstrip("/") + "/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {"url": target_url}
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, headers=headers, json=payload) as resp:
            # 4xx/5xx will still attempt to parse cobalt error JSON
            try:
                data = await resp.json()
            except Exception:
                text = await resp.text()
                raise RuntimeError(
                    f"Cobalt non-JSON response: {resp.status} {text[:120]}"
                ) from None
            if resp.status != 200 and data.get("status") != "error":
                raise RuntimeError(f"Cobalt HTTP {resp.status}: {data}")
            return data


async def _handle_cobalt_response(message: Message, data: dict) -> None:
    status = data.get("status")

    if status in ("redirect", "tunnel"):
        await _fetch_and_send(message, data.get("url"), data.get("filename"))
        return

    if status == "picker":
        await _send_picker(message, data.get("picker") or [])
        return

    if status == "local-processing":
        # Best-effort: if exactly one tunnel and not HLS, try sending it directly.
        tunnels = data.get("tunnel") or []
        output = data.get("output") or {}
        is_hls = bool(data.get("isHLS"))
        if len(tunnels) == 1 and not is_hls:
            await _fetch_and_send(message, tunnels[0], output.get("filename"))
            return
        await message.reply_text(
            "This media requires local processing, which isn't supported yet."
        )
        return

    if status == "error":
        err = data.get("error", {})
        code = err.get("code") or "unknown"
        await message.reply_text(f"Failed to fetch media: {code}")
        return

    await message.reply_text("Unsupported response from Cobalt.")


@triggers(["dl"])
@usage("/dl [URL]")
@example("/dl https://www.instagram.com/reel/A1234567890/")
@description("Download media via cobalt.tools-compatible instance.")
async def dl_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    url = utils.extract_link(update.message)
    if not url:
        await update.message.reply_text("Please provide a valid URL.")
        return

    target = url.geturl() if hasattr(url, "geturl") else str(url)
    cobalt_base = config["API"].get("COBALT_URL") or "http://100.88.216.3:9000"

    try:
        data = await _cobalt_request(cobalt_base, target)
        await _handle_cobalt_response(update.message, data)
    except Exception as e:
        logger.error(f"Cobalt error: {e}")
        await update.message.reply_text("Failed to fetch media.")
