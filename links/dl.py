from typing import TYPE_CHECKING
from logging import getLogger

import yt_dlp
from io import BytesIO
from requests import get
from telegram import MessageEntity
from telegram.error import BadRequest

if TYPE_CHECKING:
    import telegram
    import telegram.ext

ydl_opts = {
    # b = best within the applied constraints
    # TG Bots can't send docs/vids bigger than 50MB
    # 3gp is terrible and makes tg servers unhappy
    "format": "b[ext!=3gp]",
    "outtmpl": "-",
    "logger": getLogger(),
    "skip_download": True,
    "age_limit": 33,
    "geo_bypass": True,
}


class DLBufferUsedWarning(Exception):
    pass


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

    text: str
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # age and geo restriction should be bypassed in most cases
            vid_info = ydl.extract_info(video_url)
            text = ""
        except yt_dlp.utils.DownloadError as e:
            vid_info = None
            if e.msg and "Unsupported URL" in e.msg:
                text = "Unsupported URL"
            elif e.msg and "Requested format is not available" in e.msg:
                text = "No video available under 50 MB (Telegram allows only 50 MB uploads for bots)"
            else:
                text = "Could not download video"

    if text or not vid_info:
        update.message.reply_text(text or "Could not download video")
    else:
        try:
            update.message.reply_video(vid_info["url"])
        except BadRequest:
            # some vid URLs don't work, god knows why, so falling back to using a file buffer
            sent_msg = update.message.reply_text("Uploading...")

            buffer = BytesIO()
            buffer.write(get(vid_info["url"], stream=True).content)
            buffer.seek(0)

            update.message.reply_video(buffer)
            sent_msg.delete()

            buffer.close()
            # log that a file buffer was used instead of a URL
            raise DLBufferUsedWarning(
                "Couldn't use URL for /dl, used a file buffer instead"
            )
