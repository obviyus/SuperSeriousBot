from typing import Dict
from urllib.parse import ParseResult, urlparse

import httpx
import requests
import yt_dlp
from asyncpraw.exceptions import InvalidURL
from asyncprawcore import Forbidden, NotFound
from redvid import Downloader
from telegram import InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import commands
import utils
from config.logger import logger
from config.options import config
from utils.decorators import description, example, triggers, usage
from .reddit_comment import reddit

reddit_downloader = Downloader()
reddit_downloader.auto_max = True
reddit_downloader.max_s = 45 * (1 << 20)

MAX_IMAGE_COUNT = 10

ydl = yt_dlp.YoutubeDL(
    {
        "format": "b[filesize<=?50M]",
        "outtmpl": "-",
        "logger": logger,
        "skip_download": True,
        "age_limit": 33,
        "geo_bypass": True,
        "playlistend": 1,
    }
)


async def yt_dl_downloader(url: ParseResult) -> str:
    info = ydl.extract_info(url.geturl(), download=False)

    if "url" not in info:
        raise Exception("Could not download video.")

    return info["url"]


async def download_imgur(parsed_url, count) -> list[Dict]:
    imgur_hash: str = parsed_url.path.split("/")[-1]

    imgur_request_url: str = f"https://api.imgur.com/3/album/{imgur_hash}/images"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                imgur_request_url,
                headers={
                    "Authorization": f"Client-ID {config['API']['IMGUR_API_KEY']}"
                },
            )
    except requests.RequestException:
        return []

    if response.status_code == 200:
        return [{"image": img["link"]} for img in response.json()["data"]][:count]
    else:
        return [{"image": parsed_url.geturl()}]


async def download_reddit_video(parsed_url: str, message: Message):
    reddit_downloader.url = parsed_url
    try:
        file_path = reddit_downloader.download()
        if file_path == 0:
            await message.reply_text("Video too large to send over Telegram.")
            return
        if file_path == 2:
            file_path = reddit_downloader.file_name

        # The Reddit video player plays audio and video in 2 channels, which is why downloading the file is
        # necessary: https://github.com/elmoiv/redvid/discussions/29#discussioncomment-3039189
        await message.reply_video(
            video=open(file_path, "rb"),
        )

        return
    except Exception as e:
        logger.error(e)


async def instagram_download(parsed_url: str, message: Message):
    if not config["API"]["RAPID_API_KEY"]:
        await message.reply_text(
            "Instagram API key missing, command disabled. Contact the bot owner to enable it."
        )
        return

    headers = {
        "X-RapidAPI-Key": config["API"]["RAPID_API_KEY"],
        "X-RapidAPI-Host": "instagram-media-downloader.p.rapidapi.com",
    }

    response = requests.request(
        "GET",
        "https://instagram-media-downloader.p.rapidapi.com/rapid/post.php",
        headers=headers,
        params={
            "url": parsed_url,
        },
    ).json()

    if "video" in response:
        await message.reply_video(
            video=response["video"],
        )
        return

    await message.reply_text("Unhandled case of download.")


@usage("/dl")
@example("/dl")
@triggers(["dl"])
@description("Reply to a message to download the media attached to a URL.")
async def downloader(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Download the image or video from a link.
    """
    # Parse URL entity in a given link
    url = utils.extract_link(update.message)
    if not url:
        await commands.usage_string(update.message, downloader)
        return

    image_list = []

    # Prefix the URL with the scheme if it is missing
    if not url.scheme:
        original_url = "https://" + url.geturl()
        url = urlparse(original_url)

    hostname = url.hostname.replace("www.", "").replace("m.", "").replace("old.", "")
    match hostname:
        case "imgur.com":
            image_list = await download_imgur(url, MAX_IMAGE_COUNT)
        case ("i.redd.it" | "preview.redd.it"):
            image_list = [{"image": url.geturl()}]
        case "v.redd.it":
            await download_reddit_video(url.geturl(), update.message)
            return
        case "instagram.com":
            await instagram_download(url.geturl(), update.message)
            return
        case ("redd.it" | "reddit.com"):
            try:
                post = await reddit.submission(url=url.geturl().replace("old.", ""))
                if hasattr(post, "crosspost_parent") and post.crosspost_parent:
                    post = await reddit.submission(
                        id=post.crosspost_parent.split("_")[1]
                    )
            except (InvalidURL, NotFound):
                await update.message.reply_text(
                    "URL is invalid or the subreddit is banned."
                )
                return
            except Forbidden:
                await update.message.reply_text("Subreddit is quarantined or private.")
                return
            except Exception as e:
                logger.error(e)
                await update.message.reply_text("Something went wrong.")
                return

            if hasattr(post, "is_gallery"):
                # If url is a reddit gallery
                media_ids = [i["media_id"] for i in post.gallery_data["items"]]
                image_list = [
                    {"image": post.media_metadata[media_id]["p"][-1]["u"]}
                    for media_id in media_ids[:MAX_IMAGE_COUNT]
                ]
            elif hasattr(post, "is_video") or post.domain == "v.redd.it":
                await download_reddit_video(post.url, update.message)
                return
            elif post.domain == "i.redd.it":
                # If derived url is a single image or video
                image_list = [{"image": post.url}]
            elif post.domain == "imgur.com":
                # If post is an imgur album/image
                parsed_imgur_url = urlparse(post.url)
                image_list = await download_imgur(parsed_imgur_url, MAX_IMAGE_COUNT)

    if not image_list:
        try:
            await update.message.reply_video(await yt_dl_downloader(url))
            return
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("Could not download video.")
            return
    else:
        try:
            await update.message.reply_media_group(
                [
                    InputMediaPhoto(content["image"])
                    if "image" in content
                    else InputMediaVideo(content["video"])
                    for content in image_list
                ]
            )
        except BadRequest:
            await update.message.reply_text(
                "Could not download media. The file was probably deleted."
            )
            return
