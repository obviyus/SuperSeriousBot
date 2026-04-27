import io

from telegram import InputFile, InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import utils
from config.logger import logger
from config.options import config
from utils.decorators import command
from utils.messages import get_message

MAX_MEDIA_COUNT = 10
MAX_DOWNLOAD_SIZE = 47 * (1 << 20)  # ~47 MB cap to stay under Telegram limits


async def _fetch_and_send(message: Message, url: str, filename: str | None) -> None:
    try:
        import aiohttp

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
                async for chunk in resp.content.iter_chunked(262144):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_SIZE:
                        raise RuntimeError("File too large to download in memory.")
                    buffer.write(chunk)

                buffer.seek(0)
                content_type = resp.headers.get("Content-Type")
        safe_name = filename or "file"
        file = InputFile(buffer, filename=safe_name)
        target_name = safe_name.lower()

        if target_name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")) or (
            content_type and content_type.startswith("image/")
        ):
            await message.reply_photo(photo=file)
            return
        if target_name.endswith((".mp4", ".mov", ".webm", ".mkv", ".avi")) or (
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


@command(
    triggers=["dl"],
    usage="/dl [URL]",
    example="/dl https://www.instagram.com/reel/A1234567890/",
    description="Download media via cobalt.tools-compatible instance.",
)
async def dl_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    import aiohttp

    message = get_message(update)
    if not message:
        return

    url = utils.extract_link(message)
    if not url:
        await message.reply_text("Please provide a valid URL.")
        return

    target = url.geturl() if hasattr(url, "geturl") else str(url)
    endpoint = (config["API"].get("COBALT_URL") or "http://100.69.132.40:9000").rstrip("/") + "/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json={"url": target},
            ) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Cobalt non-JSON response: {resp.status} {text[:120]}"
                    ) from None
                if resp.status != 200 and data.get("status") != "error":
                    raise RuntimeError(f"Cobalt HTTP {resp.status}: {data}")

        status = data.get("status")
        if status in {"redirect", "tunnel"}:
            media_url = data.get("url")
            if media_url:
                await _fetch_and_send(message, media_url, data.get("filename"))
            return

        if status == "picker":
            media_group = []
            for item in (data.get("picker") or [])[:MAX_MEDIA_COUNT]:
                media_url = item.get("url")
                media_type = (item.get("type") or "").lower()
                if not media_url:
                    continue
                if media_type == "photo" or media_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                    media_group.append(InputMediaPhoto(media_url))
                else:
                    media_group.append(InputMediaVideo(media_url))
            if not media_group:
                await message.reply_text("No media found.")
                return
            try:
                await message.reply_media_group(media_group)
            except BadRequest as e:
                logger.error(f"Failed to send media group: {e}")
                await message.reply_text("Media unavailable or too large.")
            return

        if status == "local-processing":
            tunnels = data.get("tunnel") or []
            output = data.get("output") or {}
            if len(tunnels) == 1 and not bool(data.get("isHLS")):
                await _fetch_and_send(message, tunnels[0], output.get("filename"))
                return
            await message.reply_text(
                "This media requires local processing, which isn't supported yet."
            )
            return

        if status == "error":
            err = data.get("error", {})
            await message.reply_text(
                f"Failed to fetch media: {err.get('code') or 'unknown'}"
            )
            return

        await message.reply_text("Unsupported response from Cobalt.")
    except Exception as e:
        logger.error(f"Cobalt error: {e}")
        await message.reply_text("Failed to fetch media.")
