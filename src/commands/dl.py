import asyncio
import os
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List
from urllib.parse import urlparse

import aiohttp
from telegram import InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from yt_dlp import YoutubeDL

import utils
from config.logger import logger
from config.options import config
from utils.decorators import description, example, triggers, usage

MAX_IMAGE_COUNT = 10
MAX_VIDEO_SIZE = 45 * (1 << 20)  # 45 MB


class MediaType(Enum):
    IMAGE = auto()
    VIDEO = auto()


@dataclass
class Media:
    url: str
    type: MediaType


class MediaDownloader:
    EMBEDEZ_API_URL = "https://embedez.com/api/v1/providers/combined"
    SUPPORTED_DOMAINS = [
        "instagram.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "ifunny.co",
        "reddit.com",
        "v.redd.it",
        "snapchat.com",
        "facebook.com",
        "bilibili.com",
    ]

    def __init__(self):
        self.ydl = YoutubeDL(
            {
                "format": f"b[filesize<=?{MAX_VIDEO_SIZE}]",
                "outtmpl": "%(id)s",
                "logger": logger,
                "age_limit": 33,
                "geo_bypass": True,
                "playlistend": 1,
            }
        )

        # Check if API key is available
        if "EMBEDEZ_API_KEY" not in config.get("API", {}):
            logger.warning(
                "EMBEDEZ_API_KEY not found in config, some downloads may fail"
            )

    async def download_media(self, url: str, message: Message) -> None:
        """Main handler to download media from a URL"""
        try:
            parsed_url = urlparse(url)
            hostname = (parsed_url.hostname or "").lower().removeprefix("www.")

            # Special case for v.redd.it URLs - convert to full reddit URL if needed
            if hostname == "v.redd.it":
                # Extract the ID from v.redd.it URL
                video_id = parsed_url.path.strip("/")
                if video_id:
                    # Try with embedez directly first
                    await self._handle_with_embedez(url, message)
                    return

            domain = next((d for d in self.SUPPORTED_DOMAINS if d in hostname), None)

            if domain:
                await self._handle_with_embedez(url, message)
            elif "youtu" in hostname:  # YouTube requires special handling
                await self._handle_youtube(url, message)
            else:
                await message.reply_text("Unsupported URL format.")
        except Exception as e:
            logger.error(f"Error handling {url}: {str(e)}")
            await message.reply_text(f"Failed to download content: {str(e)}")

    async def _handle_with_embedez(self, url: str, message: Message) -> None:
        """Handle media download using embedez API"""
        if "EMBEDEZ_API_KEY" not in config.get("API", {}):
            await message.reply_text("API key missing. Contact bot owner.")
            return

        async with aiohttp.ClientSession() as session:
            try:
                headers = {
                    "Authorization": f"Bearer {config['API']['EMBEDEZ_API_KEY']}"
                }
                params = {"q": url}

                async with session.get(
                    self.EMBEDEZ_API_URL, headers=headers, params=params
                ) as response:
                    if response.status != 200:
                        logger.error(f"embedez API error: {response.status}")
                        await message.reply_text("Failed to fetch content.")
                        return

                    data = await response.json()

                    if data.get("error"):
                        error_msg = data.get("message", "Unknown error")
                        logger.error(f"embedez API error: {error_msg}")
                        await message.reply_text(
                            f"Failed to fetch content: {error_msg}"
                        )
                        return

                    # Process media based on response structure
                    media_list = await self._process_embedez_response(data)
                    if media_list:
                        await self.send_media_group(message, media_list)
                    else:
                        await message.reply_text("No media found in the response.")

            except aiohttp.ClientError as e:
                logger.error(f"embedez API request error: {e}")
                await message.reply_text("Failed to download content.")

    async def _process_embedez_response(self, data: dict) -> List[Media]:
        """Process embedez API response and extract media URLs"""
        media_list = []

        # Check if response has the expected structure
        if "success" in data and data.get("success") and "data" in data:
            response_data = data["data"]

            # Check for media in the content section
            if "content" in response_data and "media" in response_data["content"]:
                media_items = response_data["content"]["media"]
                if isinstance(media_items, list):
                    for item in media_items[:MAX_IMAGE_COUNT]:
                        if (
                            "type" in item
                            and "source" in item
                            and "url" in item["source"]
                        ):
                            media_type = (
                                MediaType.VIDEO
                                if item["type"] == "video"
                                else MediaType.IMAGE
                            )
                            media_list.append(
                                Media(url=item["source"]["url"], type=media_type)
                            )

            # If no media found in content.media, look for a single media item in content
            if not media_list and "content" in response_data:
                content = response_data["content"]
                # Check for source.url structure
                if "source" in content and "url" in content["source"]:
                    media_type = (
                        MediaType.VIDEO
                        if content.get("type") == "video"
                        else MediaType.IMAGE
                    )
                    media_list.append(
                        Media(url=content["source"]["url"], type=media_type)
                    )
                # For Reddit videos, sometimes the structure is different
                elif "url" in content and isinstance(content["url"], str):
                    # Assume it's a video for reddit URLs
                    video_url = content["url"]
                    if "v.redd.it" in video_url or video_url.endswith((".mp4", ".mov")):
                        media_list.append(Media(url=video_url, type=MediaType.VIDEO))
                    else:
                        media_list.append(Media(url=video_url, type=MediaType.IMAGE))

        # Fallback for other response structures
        if not media_list:
            # The structure might vary depending on the source platform
            # Check common patterns
            if "media" in data:
                media_items = data["media"]
                if isinstance(media_items, list):
                    for item in media_items[:MAX_IMAGE_COUNT]:
                        if "type" in item and "url" in item:
                            media_type = (
                                MediaType.VIDEO
                                if item["type"] == "video"
                                else MediaType.IMAGE
                            )
                            media_list.append(Media(url=item["url"], type=media_type))
                elif isinstance(media_items, dict) and "url" in media_items:
                    # Single media item
                    media_type = (
                        MediaType.VIDEO
                        if media_items.get("type") == "video"
                        else MediaType.IMAGE
                    )
                    media_list.append(Media(url=media_items["url"], type=media_type))

            # Last fallback - look for direct URL
            if not media_list and "url" in data:
                # Check if it's a video URL
                if data.get("type") == "video" or data["url"].endswith(
                    (".mp4", ".mov", ".avi")
                ):
                    media_list.append(Media(url=data["url"], type=MediaType.VIDEO))
                else:
                    media_list.append(Media(url=data["url"], type=MediaType.IMAGE))

        # Log extracted media for debugging
        if media_list:
            logger.info(f"Extracted {len(media_list)} media items")
        else:
            logger.warning(f"No media extracted from response: {str(data)}...")

        return media_list

    async def _handle_youtube(self, url: str, message: Message) -> None:
        """Handle YouTube video download"""
        try:
            info = await asyncio.get_running_loop().run_in_executor(
                None, lambda: self.ydl.extract_info(url, download=True)
            )
            video_path = info["id"]

            await message.reply_video(video=open(video_path, "rb"))
            os.remove(video_path)
        except Exception as e:
            logger.error(f"YouTube download error: {e}")
            await message.reply_text("Failed to download YouTube video.")

    async def send_media_group(self, message: Message, media_list: List[Media]) -> None:
        """Send media group with proper error handling"""
        if not media_list:
            await message.reply_text("No media found.")
            return

        # For single media item, send directly to avoid media group issues
        if len(media_list) == 1:
            media = media_list[0]
            try:
                if media.type == MediaType.IMAGE:
                    await message.reply_photo(photo=media.url)
                else:
                    await message.reply_video(video=media.url)
                return
            except BadRequest as e:
                logger.error(f"Failed to send single media: {str(e)}")
                await message.reply_text("Media unavailable or too large.")
                return

        # For multiple media items, use media group
        try:
            await message.reply_media_group(
                [
                    (InputMediaPhoto if m.type == MediaType.IMAGE else InputMediaVideo)(
                        m.url
                    )
                    for m in media_list[:10]
                ]
            )
        except BadRequest as e:
            logger.error(f"Failed to send media group: {str(e)}")
            await message.reply_text("Media unavailable or too large.")


downloader = MediaDownloader()


@triggers(["dl"])
@usage("/dl [URL]")
@example("/dl https://www.instagram.com/p/abcdefg/")
@description(
    "Download media from Reddit, Imgur, Instagram, TikTok, Twitter, and other platforms."
)
async def dl_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Download media from supported platforms."""
    if not update.message:
        return

    url = utils.extract_link(update.message)
    if not url:
        await update.message.reply_text("Please provide a valid URL.")
        return

    url_string = url if isinstance(url, str) else url.geturl()
    await downloader.download_media(url_string, update.message)
