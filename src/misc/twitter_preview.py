import httpx
from dateparser import parse
from telegram import InputMediaPhoto, InputMediaVideo, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import utils
from commands.dl import yt_dl_downloader
from config import config

TWEET_ENDPOINT = "https://api.twitter.com/2/tweets"


async def twitter_preview(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Preview a tweet."""
    url = utils.extract_link(update.message)
    if (
        not url
        or not url.hostname
        or "twitter" not in url.hostname
        or "TWITTER_BEARER_TOKEN" not in config["API"]
    ):
        return

    tweet_id = url.path.split("/")[-1]
    if not tweet_id:
        return

    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.get(
            TWEET_ENDPOINT,
            params={
                "ids": tweet_id,
                "expansions": "author_id,attachments.media_keys",
                "tweet.fields": "created_at,id,text",
                "user.fields": "name,username,verified",
                "media.fields": "type,url,preview_image_url",
            },
            headers={
                "Authorization": f"Bearer {config['API']['TWITTER_BEARER_TOKEN']}",
            },
        )

    if response.status_code != 200:
        return

    data = response.json()
    if not data["data"]:
        return

    user = data["includes"]["users"][0]
    attachments = data["includes"]["media"] if "media" in data["includes"] else []
    data = data["data"][0]

    text = f"""<b>{user['name']}</b>\n(@{user['username']}{" ✅" if user['verified'] else ""})"""
    text += f" <i>{await utils.readable_time(int(parse(data['created_at']).timestamp()))} ago</i>"
    text += f"\n\n{data['text']}"

    media_group = []
    for index, media in enumerate(attachments):
        if media["type"] == "photo":
            content_url = media["url"]
        else:
            try:
                # If a downloadable non-image type is available, send only that
                content_url = await yt_dl_downloader(url)
                media_group = [
                    InputMediaVideo(
                        content_url, caption=text, parse_mode=ParseMode.HTML
                    )
                ]
                break
            except Exception as _:
                content_url = media["preview_image_url"]

        media_group.append(
            InputMediaPhoto(
                content_url,
                caption=text if index == 0 else None,
                parse_mode=ParseMode.HTML,
            )
        )

    if len(media_group):
        try:
            await update.message.reply_media_group(
                media_group,
            )
        except BadRequest:
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
            )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )
