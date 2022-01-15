import requests
from urllib.parse import urlparse
from configuration import config

from .randdit import reddit
from praw.exceptions import InvalidURL
from prawcore.exceptions import NotFound, Forbidden

from telegram import InputMediaPhoto, InputMediaDocument, MessageEntity
from telegram.error import BadRequest, RetryAfter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

# limit for private chats should always be larger than groups
MAX_IMAGES_PRIVATE = 80
MAX_IMAGES_GROUPS = 40


def get_imgur_url_list(parsed_url, count):
    headers: dict = {"Authorization": f"Client-ID {config['IMGUR_KEY']}"}
    imgur_hash: str = parsed_url.path.split("/")[-1]
    imgur_request_url: str = f"https://api.imgur.com/3/album/{imgur_hash}/images"
    try:
        resp = requests.get(imgur_request_url, headers=headers)
    except requests.RequestException:
        return []

    if resp.ok:
        return [img["link"] for img in resp.json()["data"]][:count]
    else:
        return [parsed_url.geturl()]


def album(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Download reddit and imgur albums"""
    original_message: "telegram.Message" = update.message
    send_as: str = "images"
    img_url_list: list = []
    count: int = 5

    message: "telegram.Message"
    if update.message.reply_to_message:
        message = update.message.reply_to_message
    elif update.message:
        message = update.message
    else:
        return

    entities: list = list(message.parse_entities([MessageEntity.URL]).values())

    if entities:
        original_url = entities[0]
    else:
        original_message.reply_text(
            "*Usage:* \n`/album {REDDIT/IMGUR ALBUM LINK} [files] [COUNT]\n"
            "*Example:* `/album imgur.com/gallery/H5ijXa1`\n"
            'The count is optional and can be a number or "all", '
            f"default is 5, max is {MAX_IMAGES_GROUPS} in groups "
            f"and {MAX_IMAGES_PRIVATE} in private\n"
            'Add "files" (before the count) to download uncompressed'
        )
        return

    # get the count within limits
    if context.args and context.args[-1].isdigit():
        count = int(context.args[-1]) or 1
    elif context.args and "all" in context.args:
        count = MAX_IMAGES_PRIVATE

    if update.effective_chat.type == "private" and count > MAX_IMAGES_PRIVATE:  # type: ignore
        count = MAX_IMAGES_PRIVATE
    elif update.effective_chat.type in ["group", "supergroup"] and count > MAX_IMAGES_GROUPS:  # type: ignore
        count = MAX_IMAGES_GROUPS

    if context.args and ("files" in context.args or "file" in context.args):
        send_as = "files"

    parsed_original_url = urlparse(original_url)

    # need to have the scheme in the url for praw
    if not parsed_original_url.scheme:
        original_url = "https://" + original_url
        parsed_original_url = urlparse(original_url)

    if "imgur" in parsed_original_url.hostname:  # type: ignore
        img_url_list = get_imgur_url_list(parsed_original_url, count)
    elif parsed_original_url.hostname in ["i.redd.it", "v.redd.it", "preview.redd.it"]:
        # given url is itself a single image or video
        img_url_list = [original_url]
    elif "redd.it" in parsed_original_url.hostname or "reddit.com" in parsed_original_url.hostname:  # type: ignore
        try:
            post = reddit.submission(url=original_url)
            post._fetch()
        except (InvalidURL, NotFound):
            original_message.reply_text("URL is invalid or the subreddit is banned")
            return
        except Forbidden:
            original_message.reply_text("Subreddit is quarantined or private")
            return

        # reddit doesn't have a very clean, obvious way to detect deleted post
        # this might not work for all cases but there's no documentation about it
        # so this will have to do
        if post.removed_by_category:
            original_message.reply_text("Post is deleted/removed")
            return

        if hasattr(post, "is_gallery"):
            # if url is a reddit gallery
            media_ids = [i["media_id"] for i in post.gallery_data["items"]]
            img_url_list = [
                post.media_metadata[media_id]["p"][-1]["u"]
                for media_id in media_ids[:count]
            ]
        elif post.domain in ["i.redd.it", "v.redd.it"]:
            # if derived url is a single image or video
            img_url_list = [post.url]
        elif post.domain == "imgur.com":
            # if post is an imgur album/image
            parsed_imgur_url = urlparse(post.url)
            img_url_list = get_imgur_url_list(parsed_imgur_url, count)

    if not img_url_list:
        original_message.reply_text("Invalid URL")
    else:
        # Can only send 10 images in an album at a time
        chunked_url_list = [
            img_url_list[pos : pos + 10] for pos in range(0, len(img_url_list), 10)
        ]

        if send_as == "images":
            InputMediaTarget = InputMediaPhoto
        else:
            InputMediaTarget = InputMediaDocument

        try:
            for chunk in chunked_url_list:
                try:
                    original_message.reply_media_group(
                        [InputMediaTarget(img_url) for img_url in chunk]
                    )
                except BadRequest:
                    original_message.reply_text("Sorry, we couldn't download that")
        except RetryAfter:
            original_message.reply_text("Flood limit exceeded")


# TODO: gifs, videos
