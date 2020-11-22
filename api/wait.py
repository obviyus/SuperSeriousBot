import requests
import urllib.parse
import json


def wait(update, context):
    """What Anime Is This?"""
    try:
        message = update.message.reply_to_message

        file = context.bot.getFile(message.photo[-1].file_id)

        query = f"https://trace.moe/api/search?url={file.file_path}"
        response = requests.get(query).json()["docs"][0]

        similarity = round(response["similarity"] * 100, 2)
        title = response["title_english"]
        episode = response["episode"]
        season = response["season"]
        filename = urllib.parse.quote(response["filename"])
        anilist_id = response["anilist_id"]
        at = response["at"]
        tokenthumb = response["tokenthumb"]

        preview = f"https://media.trace.moe/video/{anilist_id}/{filename}?t={at}&token={tokenthumb}&mute"
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
