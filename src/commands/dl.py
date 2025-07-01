import asyncio
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional
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

# Constants
MAX_IMAGE_COUNT = 10
MAX_VIDEO_SIZE = 45 * (1 << 20)  # 45 MB
APKG_KEY = "EMBEDEZ_API_KEY"
API_SECTION = "API"
REDDIT_VIDEO_QUALITIES = [
    "DASH_1080.mp4",
    "DASH_720.mp4",
    "DASH_480.mp4",
    "DASH_360.mp4",
]


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

        # Validate API configuration
        self._validate_api_config()

    def _get_hostname(self, url: str) -> str:
        """Extract and normalize hostname from URL."""
        parsed_url = urlparse(url)
        return (parsed_url.hostname or "").lower().removeprefix("www.")

    def _is_supported_domain(self, hostname: str) -> bool:
        """Check if hostname is in supported domains."""
        return any(domain in hostname for domain in self.SUPPORTED_DOMAINS)

    async def _handle_vreddit_direct(self, url: str, message: Message) -> bool:
        """Handle v.redd.it videos directly by trying different quality URLs.
        Returns True if successful, False if should fallback to other methods.
        """
        base_url = url.rstrip("/")

        async with aiohttp.ClientSession() as session:
            for quality in REDDIT_VIDEO_QUALITIES:
                video_url = f"{base_url}/{quality}"
                try:
                    # Check if the video URL exists
                    async with session.head(video_url) as response:
                        if response.status == 200:
                            # Try to send the video
                            try:
                                await message.reply_video(video=video_url)
                                logger.info(
                                    f"Successfully sent v.redd.it video with quality {quality}"
                                )
                                return True
                            except BadRequest as e:
                                logger.warning(
                                    f"Failed to send v.redd.it video {quality}: {e}"
                                )
                                # Continue to try other qualities or fallback
                                continue
                except aiohttp.ClientError:
                    # URL doesn't exist, try next quality
                    continue

        logger.info("No direct v.redd.it video URLs worked, will try fallback methods")
        return False

    async def download_media(self, url: str, message: Message) -> None:
        """Main handler to download media from a URL."""
        try:
            hostname = self._get_hostname(url)

            # Special handling for v.redd.it - try direct approach first
            if hostname == "v.redd.it":
                if await self._handle_vreddit_direct(url, message):
                    return  # Success, no need for fallback
                # If direct method failed, fall through to embedez

            # Try embedez first for supported domains
            if hostname == "v.redd.it" or self._is_supported_domain(hostname):
                success = await self._handle_with_embedez(url, message)
                if success:
                    return
                # If embedez failed, try yt-dlp as fallback
                await self._handle_ytdlp(url, message)
            else:
                # For unsupported domains, try yt-dlp directly
                await self._handle_ytdlp(url, message)
        except Exception as e:
            logger.error(f"Error handling {url}: {str(e)}")
            # Silent failure - don't notify user of technical errors

    def _validate_api_config(self) -> None:
        """Validate API configuration and log warnings."""
        section = config.get(API_SECTION, {})
        if not section.get(APKG_KEY):
            logger.warning(
                "EMBEDEZ_API_KEY not found or empty, some downloads may fail"
            )

    def _has_api_key(self) -> bool:
        """Check if API key is available and non-empty."""
        section = config.get(API_SECTION, {})
        return bool(section.get(APKG_KEY))

    async def _handle_with_embedez(self, url: str, message: Message) -> bool:
        """Handle media download using embedez API."""
        if not self._has_api_key():
            logger.warning("API key missing for embedez")
            return False

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"Authorization": f"Bearer {config[API_SECTION][APKG_KEY]}"}
                params = {"q": url}

                async with session.get(
                    self.EMBEDEZ_API_URL, headers=headers, params=params
                ) as response:
                    if response.status == 429:  # Rate limit
                        logger.warning("Embedez API rate limit reached")
                        return False
                    elif response.status == 401:  # Unauthorized
                        logger.warning("Embedez API unauthorized - invalid key")
                        return False
                    elif response.status != 200:
                        logger.warning(f"Embedez API returned status {response.status}")
                        return False

                    data = await response.json()

                    if data.get("error"):
                        error_msg = data.get("message", "Unknown error")
                        logger.warning(f"Embedez API error: {error_msg}")
                        return False

                    # Process and send media
                    media_list = await self._process_embedez_response(data)
                    if media_list:
                        await self.send_media_group(message, media_list)
                        return True
                    else:
                        logger.info("No media found in embedez response")
                        return False

            except aiohttp.ClientError as e:
                logger.warning(f"Embedez network error: {str(e)}")
                return False

    def _extract_media_from_list(self, media_items: List[Dict]) -> List[Media]:
        """Extract media from a list of media items."""
        media_list = []
        for item in media_items[:MAX_IMAGE_COUNT]:
            if "type" in item and "source" in item and "url" in item["source"]:
                media_type = (
                    MediaType.VIDEO if item["type"] == "video" else MediaType.IMAGE
                )
                media_list.append(Media(url=item["source"]["url"], type=media_type))
        return media_list

    def _extract_single_media(self, content: Dict) -> Optional[Media]:
        """Extract a single media item from content."""
        # Check for source.url structure
        if "source" in content and "url" in content["source"]:
            media_type = (
                MediaType.VIDEO if content.get("type") == "video" else MediaType.IMAGE
            )
            return Media(url=content["source"]["url"], type=media_type)

        # Check for direct URL in content
        if "url" in content and isinstance(content["url"], str):
            video_url = content["url"]
            if self._is_video_url(video_url):
                return Media(url=video_url, type=MediaType.VIDEO)
            else:
                return Media(url=video_url, type=MediaType.IMAGE)

        return None

    def _is_video_url(self, url: str) -> bool:
        """Check if URL is likely a video based on domain or extension."""
        return "v.redd.it" in url or url.endswith((".mp4", ".mov", ".avi"))

    def _get_media_type(self, item: Dict) -> MediaType:
        """Determine media type from item dictionary."""
        return MediaType.VIDEO if item.get("type") == "video" else MediaType.IMAGE

    async def _process_embedez_response(self, data: Dict) -> List[Media]:
        """Process embedez API response and extract media URLs."""
        # Try structured response first
        if "success" in data and data.get("success") and "data" in data:
            media_list = self._extract_from_structured_response(data["data"])
            if media_list:
                return media_list

        # Try fallback extraction methods
        media_list = self._extract_from_fallback_patterns(data)

        # Log results
        if media_list:
            logger.info(f"Extracted {len(media_list)} media items")
        else:
            logger.warning(f"No media extracted from response: {str(data)[:100]}...")

        return media_list

    def _extract_from_structured_response(self, response_data: Dict) -> List[Media]:
        """Extract media from structured embedez response."""
        media_list = []

        if "content" not in response_data:
            return media_list

        content = response_data["content"]

        # Check for media list in content
        if "media" in content and isinstance(content["media"], list):
            media_list = self._extract_media_from_list(content["media"])

        # Check for single media item
        if not media_list:
            single_media = self._extract_single_media(content)
            if single_media:
                media_list.append(single_media)

        return media_list

    def _extract_from_fallback_patterns(self, data: Dict) -> List[Media]:
        """Extract media using fallback patterns for various response structures."""
        media_list = []

        # Check for direct media array
        if "media" in data:
            media_items = data["media"]
            if isinstance(media_items, list):
                for item in media_items[:MAX_IMAGE_COUNT]:
                    if "type" in item and "url" in item:
                        media_list.append(
                            Media(url=item["url"], type=self._get_media_type(item))
                        )
            elif isinstance(media_items, dict) and "url" in media_items:
                media_list.append(
                    Media(
                        url=media_items["url"], type=self._get_media_type(media_items)
                    )
                )

        # Check for direct URL in response
        if not media_list and "url" in data:
            media_type = (
                MediaType.VIDEO
                if self._is_video_url(data["url"]) or data.get("type") == "video"
                else MediaType.IMAGE
            )
            media_list.append(Media(url=data["url"], type=media_type))

        return media_list

    async def _handle_ytdlp(self, url: str, message: Message) -> None:
        """Handle media download using yt-dlp."""
        try:
            info = await asyncio.get_running_loop().run_in_executor(
                None, lambda: self.ydl.extract_info(url, download=True)
            )
            video_path = info["id"]

            await message.reply_video(video=open(video_path, "rb"))
            os.remove(video_path)
            return True
        except Exception as e:
            logger.error(f"yt-dlp download error: {e}")
            # Silent failure - don't notify user

    async def _send_single_media(self, message: Message, media: Media) -> bool:
        """Send a single media item. Returns True if successful."""
        try:
            if media.type == MediaType.IMAGE:
                await message.reply_photo(photo=media.url)
            else:
                await message.reply_video(video=media.url)
            return True
        except BadRequest as e:
            logger.error(f"Failed to send single media: {str(e)}")
            await message.reply_text("Media unavailable or too large.")
            return False

    async def _send_media_group(
        self, message: Message, media_list: List[Media]
    ) -> bool:
        """Send multiple media items as a group. Returns True if successful."""
        try:
            media_group = [
                (InputMediaPhoto if m.type == MediaType.IMAGE else InputMediaVideo)(
                    m.url
                )
                for m in media_list[:MAX_IMAGE_COUNT]
            ]
            await message.reply_media_group(media_group)
            return True
        except BadRequest as e:
            logger.error(f"Failed to send media group: {str(e)}")
            await message.reply_text("Media unavailable or too large.")
            return False

    async def send_media_group(self, message: Message, media_list: List[Media]) -> None:
        """Send media group with proper error handling."""
        if not media_list:
            await message.reply_text("No media found.")
            return

        # For single media item, send directly to avoid media group issues
        if len(media_list) == 1:
            await self._send_single_media(message, media_list[0])
        else:
            await self._send_media_group(message, media_list)


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

    url_string = url.geturl() if hasattr(url, "geturl") else str(url)
    await downloader.download_media(url_string, update.message)
