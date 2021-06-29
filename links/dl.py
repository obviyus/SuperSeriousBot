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
            r = ydl.extract_info(video_url, download=False)

        # Telegram imposes a hard limit of 50MB on all document types
        size = int(requests.head(r['url']).headers.get('content-length', 0)) / float(1 << 20)
        if size > 50:
            message.reply_text(f"Video size is {size}MB. Telegram only allows bots to send files < 50MB.")
        else:
            # Direct HTTP url to video is limited to 20MB
            buffer = BytesIO()
            buffer.write(requests.get(r['url'], stream=True).content)
            buffer.seek(0)

            message.reply_video(
                video=buffer
            )

    except AttributeError:
        message.reply_text(
            text="*Usage:* `/dl` in reply to link. Video filesize limited to < 50MB. The bot will download videos "
                 "on a best effort basis, i.e. highest possible quality while staying within the limit. "
        )
