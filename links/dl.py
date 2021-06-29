from io import BytesIO
from typing import TYPE_CHECKING

import requests
import youtube_dl
from telegram import MessageEntity

if TYPE_CHECKING:
    import telegram
    import telegram.ext

# Get download URL on a best effort basis; i.e. highest possible quality while keeping size under 50MB.
ydl_opts = {
    'format': 'best[filesize<50M]',
}


def dl(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Download a given video link and send as native Telegram video file"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    try:
        video_url = list(message.reply_to_message.parse_entities([MessageEntity.URL]).values())[0]
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                r = ydl.extract_info(video_url, download=False)
            except youtube_dl.utils.DownloadError:
                message.reply_text(
                    text="No available video file under 50MB."
                )

        # Telegram imposes a hard limit of 50MB on all document types
        # Direct HTTP url to video is limited to 20MB
        buffer = BytesIO()
        buffer.write(requests.get(r['url'], stream=True).content)
        buffer.seek(0)

        message.reply_video(
            video=buffer
        )

    except AttributeError:
        message.reply_text(
            text="*Usage:* `/dl` in reply to a link. Video file-size limited to < 50MB. The bot will download videos "
                 "on a best effort basis, i.e. highest possible quality while staying within the limit. "
        )
