import os

import yt_dlp
from redvid import Downloader
from telegram import MessageEntity, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import internal
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

    if update.message.reply_to_message:
        url = update.message.reply_to_message.parse_entities(
            [MessageEntity.URL]
        ).values()
    elif context.args:
        url = update.message.parse_entities([MessageEntity.URL]).values()
    else:
        await internal.usage_string(update.message)
        return

    url = next(iter(url), None)
    if not url:
        await update.message.reply_text("Invalid URL.")
        return

    # Add special handler for Reddit URLs
    if "reddit.com" in url or "redd.it" in url:
        reddit.url = url
        try:
            file_path = reddit.download()
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
            info = ydl.extract_info(url, download=False)
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
            return
