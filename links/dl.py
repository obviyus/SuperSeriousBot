import logging
import os
from typing import TYPE_CHECKING
from logging import getLogger
import yt_dlp
from redvid import Downloader
from telegram import MessageEntity
from telegram.error import BadRequest

if TYPE_CHECKING:
    import telegram
    import telegram.ext

ydl_opts = {
    "format": "b[filesize<=?50M]",
    "outtmpl": "-",
    "logger": getLogger(),
    "skip_download": True,
    "age_limit": 33,
    "geo_bypass": True,
}

reddit = Downloader()
reddit.auto_max = True
reddit.max_s = 50 * (1 << 20)


def dl(update: "telegram.Update", _: "telegram.ext.CallbackContext") -> None:
    """Download a given video link and send as native Telegram video file"""
    message: "telegram.Message"
    if update.message.reply_to_message:
        message = update.message.reply_to_message
    elif update.message:
        message = update.message
    else:
        return

    entities: list = list(message.parse_entities([MessageEntity.URL]).values())

    if entities:
        video_url = entities[0]
    else:
        update.message.reply_text(
            text=(
                "*Usage:* `/dl {LINK}` or reply to a link.\n"
                "*Example:* `/dl` https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
                "Video size is limited to 50MB. The bot will download videos on a best "
                "effort basis, i.e. highest possible quality while staying within the limit."
            ),
            disable_web_page_preview=True,
        )
        return

    # Add special handling for Reddit links
    if "reddit" in video_url or "redd.it" in video_url:
        reddit.url = video_url
        try:
            file_path = reddit.download()

            update.message.reply_video(
                video=open(file_path, "rb"),
            )

            os.remove(file_path)
        except Exception as e:
            logging.error(e)
            update.message.reply_text(
                text="Something went wrong while downloading the video. "
                "Please try again later.",
            )
        return

    text: str
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # age and geo restriction should be bypassed in most cases
            vid_info = ydl.extract_info(video_url)
        except yt_dlp.utils.DownloadError as e:
            update.message.reply_text("Unable to download video.")

    if not vid_info["url"]:
        update.message.reply_text("Unable to download video.")
    else:
        try:
            update.message.reply_video(vid_info["url"])
        except BadRequest:
            logging.error("BadRequest: %s", vid_info["url"])
            update.message.reply_text("Unable to download video.")
