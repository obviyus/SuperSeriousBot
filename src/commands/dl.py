import asyncio
import os
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional
from urllib.parse import urlparse

import aiohttp
from asyncpraw.exceptions import InvalidURL
from asyncprawcore import Forbidden, NotFound
from redvid import Downloader
from telegram import InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from yt_dlp import YoutubeDL

import utils
from config.logger import logger
from config.options import config
from utils.decorators import description, example, triggers, usage
from .reddit_comment import reddit

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
    def __init__(self):
        self.reddit_dl = Downloader(max_s=MAX_VIDEO_SIZE, auto_max=True)
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

    async def download_imgur(self, url: str) -> List[Media]:
        """Download images from Imgur"""
        imgur_hash = urlparse(url).path.split("/")[-1]
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.imgur.com/3/album/{imgur_hash}/images",
                headers={
                    "Authorization": f"Client-ID {config['API']['IMGUR_API_KEY']}"
                },
            ) as response:
                if response.status != 200:
                    return [Media(url=url, type=MediaType.IMAGE)]
                data = await response.json()
                return [
                    Media(url=img["link"], type=MediaType.IMAGE)
                    for img in data["data"][:MAX_IMAGE_COUNT]
                ]

    async def download_reddit_video(self, url: str, message: Message) -> None:
        """Download and send Reddit video"""
        self.reddit_dl.url = url
        try:
            file_path = self.reddit_dl.download()
            if isinstance(file_path, int):
                if file_path == 0:
                    await message.reply_text("Video too large for Telegram.")
                    return
                file_path = self.reddit_dl.file_name

            await message.reply_video(video=open(file_path, "rb"))
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Reddit video download error: {e}")
            await message.reply_text("Failed to download video.")

    async def process_reddit_post(
        self, url: str, message: Message
    ) -> Optional[List[Media]]:
        """Process Reddit post media"""
        try:
            post = await reddit.submission(url=url.replace("old.", ""))
            if hasattr(post, "crosspost_parent"):
                post = await reddit.submission(id=post.crosspost_parent.split("_")[1])

            if hasattr(post, "is_gallery"):
                return [
                    Media(
                        url=post.media_metadata[i["media_id"]]["p"][-1]["u"],
                        type=MediaType.IMAGE,
                    )
                    for i in post.gallery_data["items"][:MAX_IMAGE_COUNT]
                ]
            elif post.is_video or post.domain == "v.redd.it":
                await self.download_reddit_video(post.url, message)
                return None
            return [Media(url=post.url, type=MediaType.IMAGE)]
        except (InvalidURL, NotFound, Forbidden) as e:
            logger.error(f"Reddit error: {e}")
            await message.reply_text("Cannot access this Reddit content.")
            return None

    async def download_instagram(
        self, url: str, message: Message
    ) -> Optional[List[Media]]:
        """Download Instagram media"""
        if "RAPID_API_KEY" not in config["API"]:
            await message.reply_text("Instagram API key missing. Contact bot owner.")
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://instagram-media-downloader.p.rapidapi.com/rapid/post.php",
                headers={
                    "X-RapidAPI-Key": config["API"]["RAPID_API_KEY"],
                    "X-RapidAPI-Host": "instagram-media-downloader.p.rapidapi.com",
                },
                params={"url": url},
            ) as response:
                data = await response.json()

        if "video" in data:
            return [Media(url=data["video"], type=MediaType.VIDEO)]
        elif "image" in data:
            return [Media(url=data["image"], type=MediaType.IMAGE)]
        return None

    async def download_youtube(
        self, url: str, message: Message
    ) -> Optional[List[Media]]:
        """Download YouTube video"""
        try:
            info = await asyncio.get_running_loop().run_in_executor(
                None, lambda: self.ydl.extract_info(url, download=True)
            )
            video_path = info["id"]

            await message.reply_video(video=open(video_path, "rb"))
            os.remove(video_path)
            return None
        except Exception as e:
            logger.error(f"YouTube download error: {e}")
            await message.reply_text("Failed to download YouTube video.")
            return None

    async def send_media_group(self, message: Message, media_list: List[Media]) -> None:
        """Send media group with proper error handling"""
        if not media_list:
            await message.reply_text("No media found.")
            return

        try:
            await message.reply_media_group(
                [
                    (InputMediaPhoto if m.type == MediaType.IMAGE else InputMediaVideo)(
                        m.url
                    )
                    for m in media_list[:10]
                ]
            )
        except BadRequest:
            await message.reply_text("Media unavailable or too large.")


downloader = MediaDownloader()

URL_HANDLERS = {
    r"(?:www\.)?imgur\.com": downloader.download_imgur,
    r"(?:www\.|old\.)?reddit\.com|redd\.it": downloader.process_reddit_post,
    r"i\.redd\.it|preview\.redd\.it": lambda url, _: [
        Media(url=url, type=MediaType.IMAGE)
    ],
    r"v\.redd\.it": downloader.download_reddit_video,
    r"(?:www\.)?instagram\.com": downloader.download_instagram,
    r"(?:www\.)?youtu(?:\.be|be\.com)": downloader.download_youtube,
}


@triggers(["dl"])
@usage("/dl [URL]")
@example("/dl https://www.instagram.com/p/abcdefg/")
@description("Download media from Reddit, Imgur, and other platforms.")
async def dl_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Download media from supported platforms."""
    if not update.message:
        return

    url = utils.extract_link(update.message)
    if not url:
        await update.message.reply_text("Please provide a valid URL.")
        return

    parsed_url = urlparse(url if isinstance(url, str) else url.geturl())
    hostname = (
        (parsed_url.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    )

    for pattern, handler in URL_HANDLERS.items():
        if re.match(pattern, hostname, re.IGNORECASE):
            result = await handler(parsed_url.geturl(), update.message)
            if isinstance(result, list):
                await downloader.send_media_group(update.message, result)
            return

    await update.message.reply_text("Unsupported URL format.")
