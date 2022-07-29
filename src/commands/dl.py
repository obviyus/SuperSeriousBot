import os
from urllib.parse import urlparse

import httpx
import instaloader
import requests
import yt_dlp
from asyncpraw.exceptions import InvalidURL
from asyncprawcore import Forbidden, NotFound
from instaloader import Post
from redvid import Downloader
from telegram import InputMediaPhoto, InputMediaVideo, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import utils
from config.logger import logger
from config.options import config
from .reddit_comment import reddit

ydl_opts = {
    "format": "b[filesize<=?50M]",
    "outtmpl": "-",
    "logger": logger,
    "skip_download": True,
    "age_limit": 33,
    "geo_bypass": True,
}

reddit_downloader = Downloader()
reddit_downloader.auto_max = True
reddit_downloader.max_s = 50 * (1 << 20)

L = instaloader.Instaloader()
if "INSTAGRAM_SESSION_NAME" in config["API"]:
    L.load_session_from_file(config["API"]["INSTAGRAM_SESSION_NAME"])


async def get_imgur_url_list(parsed_url, count):
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


MAX_IMAGE_COUNT = 10


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Download the image or video from a link.
    """
    # Parse URL entity in a given link
    url = utils.extract_link(update)
    if not url:
        await utils.usage_string(update.message)
        return

    image_list = []

    # Prefix the URL with the scheme if it is missing
    if not url.scheme:
        original_url = "https://" + url.geturl()
        url = urlparse(original_url)

    hostname = url.hostname.replace("www.", "")
    print(hostname)

    match hostname:
        case "imgur.com":
            image_list = await get_imgur_url_list(url, MAX_IMAGE_COUNT)
        case ("i.redd.it" | "preview.redd.it"):
            image_list = [{"image": url}]
        case "instagram.com":
            # Extract shortcode
            shortcode = url.path.split("/")[-2]

            # Get the media URL
            try:
                for each in Post.from_shortcode(
                    L.context, shortcode
                ).get_sidecar_nodes():
                    if each.is_video:
                        image_list.append({"video": each.video_url})
                    else:
                        image_list.append({"image": each.display_url})
            except Exception as e:
                logger.error(e)
        case "v.redd.it":
            reddit_downloader.url = url.geturl()
            try:
                file_path = reddit_downloader.download()

                # The Reddit video player plays audio and video in 2 channels, which is why downloading the file is
                # necessary: https://github.com/elmoiv/redvid/discussions/29#discussioncomment-3039189
                await update.message.reply_video(
                    video=open(file_path, "rb"),
                )

                os.remove(file_path)
                return
            except Exception as e:
                logger.error(e)
        case ("redd.it" | "reddit.com"):  # type: ignore
            try:
                post = await reddit.submission(url=url.geturl())
                await post.load()
            except (InvalidURL, NotFound):
                await update.message.reply_text(
                    "URL is invalid or the subreddit is banned."
                )
                return
            except Forbidden:
                await update.message.reply_text("Subreddit is quarantined or private.")
                return

            # Reddit doesn't have a very clean, obvious way to detect deleted post
            # this might not work for all cases but there's no documentation about it
            # so this will have to do
            if post.removed_by_category:
                await update.message.reply_text("Post is deleted/removed.")
                return

            if hasattr(post, "is_gallery"):
                # If url is a reddit gallery
                media_ids = [i["media_id"] for i in post.gallery_data["items"]]
                image_list = [
                    {"image": post.media_metadata[media_id]["p"][-1]["u"]}
                    for media_id in media_ids[:MAX_IMAGE_COUNT]
                ]
            elif post.domain in ["i.redd.it", "v.redd.it"]:
                # If derived url is a single image or video
                image_list = [{"image": post.url}]
            elif post.domain == "imgur.com":
                # If post is an imgur album/image
                parsed_imgur_url = urlparse(post.url)
                image_list = await get_imgur_url_list(parsed_imgur_url, MAX_IMAGE_COUNT)

    if not image_list:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                try:
                    info = ydl.extract_info(url.geturl(), download=False)
                except yt_dlp.utils.DownloadError as _:
                    await update.message.reply_text("Failed to download video.")
                    return

                if not info["url"]:
                    await update.message.reply_text("Failed to download video.")
                    return
                else:
                    try:
                        await update.message.reply_video(info["url"])
                    except BadRequest:
                        logger.error("BadRequest: %s", info["url"])
                        await update.message.reply_text("Failed to download video.")
            except Exception as e:
                logger.error(e)

                await update.message.reply_text("Failed to download video.")
    else:
        await update.message.reply_media_group(
            [
                InputMediaPhoto(content["image"])
                if "image" in content
                else InputMediaVideo(content["video"])
                for content in image_list
            ]
        )
