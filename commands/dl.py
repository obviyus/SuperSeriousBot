import os

import yt_dlp
from redvid import Downloader
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import utils
from config.logger import logger

ydl_opts = {
    "format": "b[filesize<=?50M]",
    "outtmpl": "-",
    "logger": logger,
    "skip_download": True,
    "age_limit": 33,
    "geo_bypass": True,
}

reddit = Downloader()
reddit.auto_max = True
reddit.max_s = 50 * (1 << 20)


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Download video from the given link.
    """

    # Parse URL entity in a given link
    url = utils.extract_link(update)
    if not url:
        await update.message.reply_text("No URL found.")
        return

    # Add special handler for Reddit URLs
    if "reddit.com" in url or "redd.it" in url:
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
