import requests
import html
from urllib.parse import urlparse
from configuration import config

from telegram import InputMediaPhoto
from telegram.error import BadRequest
from json.decoder import JSONDecodeError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def get_imgur(parsed_url, count):
    headers: dict = {"Authorization": f"Client-ID {config['IMGUR_KEY']}"}
    imgur_hash: str = parsed_url.path.split('/')[2]
    imgur_request_url: str = f"https://api.imgur.com/3/album/{imgur_hash}/images"
    try:
        resp = requests.get(imgur_request_url, headers=headers)
    except requests.RequestException:
        return []

    if resp.ok:
        return [img["link"] for img in resp.json()["data"]][:count]
    else:
        return [parsed_url.geturl()]


def album(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Download reddit and imgur albums"""
    text: str
    img_url_list: list
    count: int
    msg = update.message

    if len(context.args) == 1:
        arg = context.args[0]
        count = 5
    elif len(context.args) >= 2:
        arg = context.args[0]
        count = int(context.args[1]) if context.args[1].isdigit() else 5
    else:
        msg.reply_text(
            text="*Usage:* \n`/album {REDDIT/IMGUR ALBUM LINK} [COUNT]`\n"
                 "*Example:* `/album imgur.com/gallery/H5ijXa1`\n"
                 "The count is optional, default is 5"
        )
        return

    parsed_arg = urlparse(arg)
    if not parsed_arg.scheme:
        parsed_arg = urlparse("https://" + arg)
    if not parsed_arg.hostname:
        msg.reply_text("Invalid URL")
        return

    if "imgur" in parsed_arg.hostname:
        img_url_list = get_imgur(parsed_arg, count)
    elif "redd.it" in parsed_arg.hostname:
        msg.reply_text("redd.it links do not work")
    elif "reddit.com" in parsed_arg.hostname and parsed_arg.path and parsed_arg.path != '/':
        headers: dict = {"User-agent": "SuperSeriousBot"}
        reddit_request_url: str = f"{parsed_arg.scheme}://{parsed_arg.hostname}{parsed_arg.path}"
        reddit_request_url = (reddit_request_url[:-1] if reddit_request_url[-1] == "/" else reddit_request_url) + ".json"
        try:
            resp = requests.get(reddit_request_url, headers=headers).json()
        except (requests.RequestException, JSONDecodeError):
            resp[0] = {"kind": "NotListing"}

        if "error" in resp and resp["error"]:
            resp[0] = {"kind": "NotListing"}
        else:
            resp_data = resp[0]["data"]["children"][0]["data"]

        if resp[0]["kind"] != "Listing":
            img_url_list = []
        elif "is_gallery" in resp_data and resp_data["is_gallery"]:
            gallery = resp_data["media_metadata"] or {}
            if resp_data["gallery_data"]:
                ordered_gallery_ids = [item["media_id"] for item in resp_data["gallery_data"]["items"]]
                ordered_gallery = [gallery[id] for id in ordered_gallery_ids]
            else:
                ordered_gallery = list(gallery.values())

            img_url_list = []
            for img in ordered_gallery[:count]:
                img_url_list.append(html.unescape(img["s"]["u"]))
        elif resp_data["domain"] == "imgur.com":
            imgur_album_url = resp_data["url"]
            parsed_imgur_album_url = urlparse(html.unescape(imgur_album_url))
            img_url_list = get_imgur(parsed_imgur_album_url, count)
        elif resp_data["domain"] == "i.redd.it":
            img_url_list = [html.unescape(resp_data["url"])]
        else:
            img_url_list = []

    if not img_url_list:
        msg.reply_text("Invalid URL")
    else:
        # Can only send 10 images in an album at a time
        chunked_url_list = [img_url_list[pos:pos + 10] for pos in range(0, len(img_url_list), 10)]
        try:
            for chunk in chunked_url_list:
                msg.reply_media_group([InputMediaPhoto(img_url) for img_url in chunk])
        except BadRequest:
            msg.reply_text("Sorry, we couldn't download that album")
