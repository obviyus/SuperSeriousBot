import asyncio
import io
import json
from html.parser import HTMLParser
from urllib.parse import ParseResult, urlparse

import aiohttp
from telegram import InputFile, InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.constants import ChatType, ReactionEmoji
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

import utils
from config.db import get_db
from config.logger import logger
from config.options import config
from utils.decorators import command
from utils.messages import get_message

MAX_MEDIA_COUNT = 10
MAX_DOWNLOAD_SIZE = 47 * (1 << 20)
DOWNLOAD_CHUNK_SIZE = 256 * 1024
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
COBALT_TIMEOUT = aiohttp.ClientTimeout(
    total=45, connect=10, sock_connect=10, sock_read=30
)
MEDIA_TIMEOUT = aiohttp.ClientTimeout(
    total=120, connect=10, sock_connect=10, sock_read=45
)


def _cobalt_endpoint() -> str | None:
    url = config.API.COBALT_URL.strip()
    return f"{url.rstrip('/')}/" if url else None


def _is_instagram_reel(url: ParseResult) -> bool:
    host = url.hostname or ""
    return host in {"instagram.com", "www.instagram.com"} and url.path.startswith(
        "/reel/"
    )


def _is_instagram_post(url: ParseResult) -> bool:
    host = url.hostname or ""
    return host in {"instagram.com", "www.instagram.com"} and url.path.startswith("/p/")


class InstagramImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta" or self.image_url:
            return
        attributes = dict(attrs)
        if attributes.get("property") == "og:image":
            self.image_url = attributes.get("content")


async def _is_auto_dl_enabled(chat_id: int) -> bool:
    async with (
        get_db() as conn,
        conn.execute(
            "SELECT auto_dl FROM group_settings WHERE chat_id = ?",
            (chat_id,),
        ) as cursor,
    ):
        row = await cursor.fetchone()
    return bool(row and row["auto_dl"])


async def _request_cobalt(
    session: aiohttp.ClientSession,
    endpoint: str,
    target: str,
) -> dict:
    async with session.post(
        endpoint,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={"url": target},
    ) as resp:
        try:
            data = await resp.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError):
            text = await resp.text()
            raise RuntimeError(
                f"Cobalt non-JSON response: {resp.status} {text[:120]}"
            ) from None
        if resp.status != 200 and data.get("status") != "error":
            raise RuntimeError(f"Cobalt HTTP {resp.status}: {data}")
    return data


def _needs_yt_dlp(url: ParseResult, data: dict) -> bool:
    if not _is_instagram_reel(url):
        return False
    if data.get("status") == "error":
        return True
    filename = data.get("filename")
    return (
        data.get("status") in {"redirect", "tunnel"}
        and isinstance(filename, str)
        and filename.lower().endswith(IMAGE_EXTENSIONS)
    )


def _extract_with_yt_dlp(target: str) -> tuple[str, str]:
    with YoutubeDL(
        {
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
    ) as yt_dlp:
        info = yt_dlp.extract_info(target, download=False)
    return info["url"], f"instagram_{info['id']}.{info['ext']}"


async def _fetch_with_yt_dlp(
    message: Message,
    session: aiohttp.ClientSession,
    target: str,
) -> None:
    media_url, filename = await asyncio.to_thread(_extract_with_yt_dlp, target)
    await _fetch_and_send(message, session, media_url, filename)


async def _fetch_instagram_image(
    message: Message,
    session: aiohttp.ClientSession,
    target: str,
) -> None:
    async with session.get(
        target,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=MEDIA_TIMEOUT,
    ) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Instagram page fetch failed: {resp.status}")
        parser = InstagramImageParser()
        parser.feed(await resp.text())

    if not parser.image_url:
        raise RuntimeError("Instagram post has no image metadata")
    shortcode = urlparse(target).path.rstrip("/").rsplit("/", 1)[-1]
    await _fetch_and_send(
        message, session, parser.image_url, f"instagram_{shortcode}.jpg"
    )


async def _fetch_and_send(
    message: Message,
    session: aiohttp.ClientSession,
    url: str,
    filename: str | None,
) -> None:
    try:
        async with session.get(url, timeout=MEDIA_TIMEOUT) as resp:
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
            async for chunk in resp.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
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

        if target_name.endswith(IMAGE_EXTENSIONS) or (
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
    except (aiohttp.ClientError, OSError, TimeoutError) as e:
        logger.error(f"Failed to download media: {e}")
        await message.reply_text("Failed to download media.")


async def _download_media(message: Message, url: ParseResult) -> None:
    endpoint = _cobalt_endpoint()
    if not endpoint:
        logger.error("COBALT_URL is not configured.")
        await message.reply_text("Download service is not configured.")
        return

    try:
        async with aiohttp.ClientSession(timeout=COBALT_TIMEOUT) as session:
            target = url.geturl()
            try:
                data = await _request_cobalt(session, endpoint, target)
            except (aiohttp.ClientError, RuntimeError, TimeoutError) as e:
                if _is_instagram_reel(url):
                    logger.warning(
                        "Cobalt failed for Instagram Reel; using yt-dlp: %s", e
                    )
                    await _fetch_with_yt_dlp(message, session, target)
                    return
                if _is_instagram_post(url):
                    logger.warning(
                        "Cobalt failed for Instagram post; using page metadata: %s", e
                    )
                    await _fetch_instagram_image(message, session, target)
                    return
                raise

            if _needs_yt_dlp(url, data):
                logger.info(
                    "Cobalt could not resolve Instagram Reel video; using yt-dlp."
                )
                await _fetch_with_yt_dlp(message, session, target)
                return

            status = data.get("status")
            if status in {"redirect", "tunnel"}:
                media_url = data.get("url")
                if not media_url:
                    await message.reply_text("No media found.")
                    return
                await _fetch_and_send(message, session, media_url, data.get("filename"))
                return

            if status == "picker":
                media_group = []
                for item in (data.get("picker") or [])[:MAX_MEDIA_COUNT]:
                    media_url = item.get("url")
                    media_type = (item.get("type") or "").lower()
                    if not media_url:
                        continue
                    if media_type == "photo" or media_url.lower().endswith(
                        (".jpg", ".jpeg", ".png", ".webp", ".gif")
                    ):
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
                    await _fetch_and_send(
                        message, session, tunnels[0], output.get("filename")
                    )
                    return
                await message.reply_text(
                    "This media requires local processing, which isn't supported yet."
                )
                return

            if status == "error":
                if _is_instagram_post(url):
                    await _fetch_instagram_image(message, session, target)
                    return
                err = data.get("error", {})
                await message.reply_text(
                    f"Failed to fetch media: {err.get('code') or 'unknown'}"
                )
                return

            await message.reply_text(
                "Download service returned an unsupported response."
            )
    except (
        aiohttp.ClientError,
        KeyError,
        RuntimeError,
        TimeoutError,
        TypeError,
        DownloadError,
    ) as e:
        logger.error(f"Media download error: {e}")
        await message.reply_text("Failed to fetch media.")


@command(
    triggers=["dl"],
    usage="/dl [URL]",
    example="/dl https://www.instagram.com/reel/A1234567890/",
    description="Download media via cobalt.tools-compatible instance.",
)
async def dl_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return

    url = utils.extract_link(message)
    if not url:
        await message.reply_text("Please provide a valid URL.")
        return

    await _download_media(message, url)


async def auto_dl_message_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or message.from_user.is_bot:
        return
    if message.chat.type == ChatType.PRIVATE:
        return
    if not await _is_auto_dl_enabled(message.chat_id):
        return

    for _entity, link in sorted(
        utils.grab_links(message).items(), key=lambda item: item[0].offset
    ):
        url = urlparse(link)
        if _is_instagram_reel(url):
            try:
                await message.set_reaction(ReactionEmoji.HIGH_VOLTAGE_SIGN)
            except BadRequest as e:
                logger.debug("Skipping auto-dl reaction: %s", e)
            await _download_media(message, url)
            return
