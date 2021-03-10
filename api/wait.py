import json
import urllib.parse
from typing import TYPE_CHECKING, Dict

import requests

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def wait(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """What Anime Is This?"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    try:
        message = message.reply_to_message

        file: telegram.File = context.bot.getFile(message.photo[-1].file_id)
        url: str = f"https://trace.moe/api/search?url={file.file_path}"

        response: Dict = requests.get(url).json()["docs"][0]

        similarity: float = round(response["similarity"] * 100, 2)
        title: str = response["title_english"]
        episode: str = response["episode"]
        season: str = response["season"]
        filename: str = urllib.parse.quote(response["filename"])
        anilist_id: str = response["anilist_id"]
        at: str = response["at"]
        tokenthumb: str = response["tokenthumb"]

        preview: str = f"https://media.trace.moe/video/{anilist_id}/{filename}?t={at}&token={tokenthumb}&mute"
        text = f"<b>{title}</b> ({season})\n" \
               f"Episode {episode}\n" \
               f"<b>Similarity: {similarity}</b>%"

        message.reply_video(
            video=preview,
            caption=text,
            parse_mode='HTML',
        )

    except AttributeError:
        text = "*Usage:* `/wait`\n" \
               "Type /wait in response to an image. Only the most similar result is returned.\n"
        update.message.reply_text(text=text)

    except json.decoder.JSONDecodeError:
        response = requests.get("https://trace.moe/api/me").json()
        text = f'Nothing returned. Remaining API quota (per minute): {response["limit"]}.'
        update.message.reply_text(text=text)
