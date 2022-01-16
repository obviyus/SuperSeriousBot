import json
from typing import Dict, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def wait(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """What Anime Is This?"""
    text: str
    try:
        if update.message and update.message.reply_to_message:
            message: "telegram.Message" = update.message.reply_to_message
        else:
            return

        file: telegram.File = context.bot.getFile(message.photo[-1].file_id)
        url: str = (
            f"https://api.trace.moe/search?anilistInfo&cutBorders&url={file.file_path}"
        )

        response: Dict = requests.get(url).json()["result"][0]

        similarity: float = round(response["similarity"] * 100, 2)
        title: str = (
            response["anilist"]["title"]["english"]
            or response["anilist"]["synonyms"][0]
            or response["anilist"]["title"]["native"]
        )

        preview: str = response["video"]
        text = f"<b>{title}</b>\n<b>Similarity: {similarity}</b>%"

        message.reply_video(
            video=preview,
            caption=text,
            parse_mode="HTML",
        )

    except AttributeError:
        text = (
            "*Usage:* `/wait`\n"
            "Type /wait in response to an image. Only the most similar result is returned.\n"
        )
        update.message.reply_text(text=text)

    except json.decoder.JSONDecodeError:
        response = requests.get("https://trace.moe/api/me").json()
        text = (
            f'Nothing returned. Remaining API quota (per minute): {response["limit"]}.'
        )
        update.message.reply_text(text=text)
