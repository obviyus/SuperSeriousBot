import os
from urllib.parse import urlparse

import requests
import yt_dlp
from asyncpraw.exceptions import InvalidURL
from asyncprawcore import Forbidden, NotFound
from redvid import Downloader
from telegram import InputMediaDocument, InputMediaPhoto, Update
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


def get_imgur_url_list(parsed_url, count):
    headers: dict = {"Authorization": f"Client-ID {config['API']['IMGUR_API_KEY']}"}
    imgur_hash: str = parsed_url.path.split("/")[-1]
    imgur_request_url: str = f"https://api.imgur.com/3/album/{imgur_hash}/images"
    try:
        resp = requests.get(imgur_request_url, headers=headers)
    except requests.RequestException:
        return []

    if resp.ok:
        return [img["link"] for img in resp.json()["data"]][:count]
    else:
        return [parsed_url.geturl()]


MAX_IMAGE_COUNT = 10


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Download video from the given link.
    """
    # Parse URL entity in a given link
    url = utils.extract_link(update)
    if not url:
        await utils.usage_string(update.message)
        return

    send_as = "images"
    if context.args and ("files" in context.args or "file" in context.args):
        send_as = "files"

    parsed_original_url = urlparse(url)
    img_url_list: list = []

    # Prefix the URL with the scheme if it is missing
    if not parsed_original_url.scheme:
        original_url = "https://" + url
        parsed_original_url = urlparse(original_url)

    if "imgur" in parsed_original_url.hostname:
        img_url_list = get_imgur_url_list(parsed_original_url, MAX_IMAGE_COUNT)
    elif parsed_original_url.hostname in ["i.redd.it", "preview.redd.it"]:
        img_url_list = [url]
    elif "v.redd.it" in parsed_original_url.hostname:
        reddit.url = url
        try:
            file_path = reddit.download()

            # The Reddit video player plays audio and video in 2 channels, which is why downloading the file is
            # necessary: https://github.com/elmoiv/redvid/discussions/29#discussioncomment-3039189
            await update.message.reply_video(
                video=open(file_path, "rb"),
            )

            os.remove(file_path)
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("Failed to download Reddit video.")
            return
    elif "redd.it" in parsed_original_url.hostname or "reddit.com" in parsed_original_url.hostname:  # type: ignore
        try:
            post = await reddit.submission(url=url)
            await post.load()
        except (InvalidURL, NotFound):
            await update.message.reply_text("URL is invalid or the subreddit is banned")
            return
        except Forbidden:
            await update.message.reply_text("Subreddit is quarantined or private")
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
            img_url_list = [
                post.media_metadata[media_id]["p"][-1]["u"]
                for media_id in media_ids[:MAX_IMAGE_COUNT]
            ]
        elif post.domain in ["i.redd.it", "v.redd.it"]:
            # If derived url is a single image or video
            img_url_list = [post.url]
        elif post.domain == "imgur.com":
            # If post is an imgur album/image
            parsed_imgur_url = urlparse(post.url)
            img_url_list = get_imgur_url_list(parsed_imgur_url, MAX_IMAGE_COUNT)

    if not img_url_list:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                try:
                    info = ydl.extract_info(url)
                except yt_dlp.utils.DownloadError as _:
                    await update.message.reply_text("Failed to download video.")

                if not info["url"]:
                    await update.message.reply_text("Failed to download video.")
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
        if send_as == "images":
            InputMediaTarget = InputMediaPhoto
        else:
            InputMediaTarget = InputMediaDocument

        await update.message.reply_media_group(
            [InputMediaTarget(img_url) for img_url in img_url_list]
        )
