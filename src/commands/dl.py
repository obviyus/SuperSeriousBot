import asyncio
import os
import re
from typing import Callable, Dict, List, Optional
from urllib.parse import ParseResult, urlparse

import aiohttp
import yt_dlp
from asyncpraw.exceptions import InvalidURL
from asyncprawcore import Forbidden, NotFound
from redvid import Downloader
from telegram import InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import utils
from config.logger import logger
from config.options import config
from utils.decorators import description, example, triggers, usage
from .reddit_comment import reddit

MAX_IMAGE_COUNT = 10
MAX_VIDEO_SIZE = 45 * (1 << 20)  # 45 MB

reddit_downloader = Downloader(max_s=MAX_VIDEO_SIZE, auto_max=True)

ydl_opts = {
    "format": f"b[filesize<=?{MAX_VIDEO_SIZE}]",
    "outtmpl": "%(id)s",
    "logger": logger,
    "age_limit": 33,
    "geo_bypass": True,
    "playlistend": 1,
}


async def download_imgur(url: str, count: int) -> List[Dict]:
    """Download images from Imgur"""
    parsed_url = urlparse(url)
    imgur_hash = parsed_url.path.split("/")[-1]
    imgur_request_url = f"https://api.imgur.com/3/album/{imgur_hash}/images"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            imgur_request_url,
            headers={"Authorization": f"Client-ID {config['API']['IMGUR_API_KEY']}"},
        ) as response:
            if response.status != 200:
                return [{"image": parsed_url.geturl()}]
            data = await response.json()
            return [{"image": img["link"]} for img in data["data"]][:count]


async def download_reddit_video(url: str, message: Message) -> None:
    """Download and send Reddit video"""
    reddit_downloader.url = url
    try:
        file_path = reddit_downloader.download()
        if file_path == 0:
            await message.reply_text("Video too large to send over Telegram.")
            return
        if file_path == 2:
            file_path = reddit_downloader.file_name

        await message.reply_video(video=open(file_path, "rb"))
        os.remove(file_path)
    except Exception as e:
        logger.error(f"Error downloading Reddit video: {e}")
        await message.reply_text("Failed to download Reddit video.")


async def download_instagram(url: str, message: Message) -> None:
    """Download and send Instagram media"""
    if "RAPID_API_KEY" not in config["API"]:
        await message.reply_text(
            "Instagram API key missing. Contact the bot owner to enable it."
        )
        return

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
        await message.reply_video(video=data["video"])
    else:
        await message.reply_text("Could not download Instagram media.")


async def download_youtube(url: str, message: Message) -> None:
    """Download and send YouTube video"""

    def download_video():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info["id"]

    try:
        video_id = await asyncio.get_running_loop().run_in_executor(
            None, download_video
        )
        await message.reply_video(video=open(video_id, "rb"))
        os.remove(video_id)
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        await message.reply_text("Failed to download YouTube video.")


async def process_reddit_post(url: str, message: Message) -> Optional[List[Dict]]:
    """Process Reddit post and return media list"""
    try:
        post = await reddit.submission(url=url.replace("old.", ""))
        if hasattr(post, "crosspost_parent") and post.crosspost_parent:
            post = await reddit.submission(id=post.crosspost_parent.split("_")[1])

        if hasattr(post, "is_gallery"):
            media_ids = [i["media_id"] for i in post.gallery_data["items"]]
            return [
                {"image": post.media_metadata[media_id]["p"][-1]["u"]}
                for media_id in media_ids[:MAX_IMAGE_COUNT]
            ]
        elif hasattr(post, "is_video") or post.domain == "v.redd.it":
            await download_reddit_video(post.url, message)
            return None
        elif post.domain == "i.redd.it":
            return [{"image": post.url}]
        elif post.domain == "imgur.com":
            parsed_imgur_url = urlparse(post.url)
            return await download_imgur(parsed_imgur_url, MAX_IMAGE_COUNT)
    except (InvalidURL, NotFound):
        await message.reply_text("URL is invalid or the subreddit is banned.")
    except Forbidden:
        await message.reply_text("Subreddit is quarantined or private.")
    except Exception as e:
        logger.error(f"Error processing Reddit post: {e}")
        await message.reply_text("Something went wrong.")
    return None


DOMAIN_HANDLERS: Dict[str, Callable] = {
    r"(?:www\.)?imgur\.com": download_imgur,
    r"i\.redd\.it|preview\.redd\.it": lambda url, _: [{"image": url.geturl()}],
    r"v\.redd\.it": download_reddit_video,
    r"(?:www\.)?instagram\.com": download_instagram,
    r"(?:www\.)?reddit\.com|redd\.it": process_reddit_post,
}


def get_domain_handler(hostname: str) -> Callable:
    for pattern, handler in DOMAIN_HANDLERS.items():
        if re.match(pattern, hostname, re.IGNORECASE):
            return handler
    return download_youtube  # Default to YouTube downloader if no match


@usage("/dl [URL]")
@example("/dl https://www.instagram.com/p/abcdefg/")
@triggers(["dl"])
@description("Download media from various supported platforms.")
async def downloader(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Download the image or video from a link."""
    message = update.message
    if not message:
        return

    url = utils.extract_link(message)
    if not url:
        await message.reply_text("Please provide a valid URL.")
        return

    if not isinstance(url, ParseResult):
        url = urlparse(url)

    if not url.scheme:
        url = urlparse(f"https://{url.geturl()}")

    hostname = url.hostname.lower() if url.hostname else ""
    if not hostname:
        await message.reply_text("Invalid URL format.")
        return

    # Remove common prefixes
    hostname = re.sub(r"^(www\.|m\.|old\.)", "", hostname)

    try:
        handler = get_domain_handler(hostname)
        result = await handler(url.geturl(), message)

        if isinstance(result, list):
            if not result:
                await message.reply_text("No media found or could not be downloaded.")
            else:
                try:
                    await message.reply_media_group(
                        [
                            (
                                InputMediaPhoto(content["image"])
                                if "image" in content
                                else InputMediaVideo(content["video"])
                            )
                            for content in result[
                                :10
                            ]  # Limit to 10 for Telegram's limit
                        ]
                    )
                except BadRequest:
                    await message.reply_text(
                        "Could not send media. The file might have been deleted or is too large."
                    )
    except Exception as e:
        logger.error(f"Error in downloader: {e}")
        await message.reply_text("An error occurred while processing your request.")
