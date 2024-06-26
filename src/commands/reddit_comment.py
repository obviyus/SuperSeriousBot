import html
import re
from urllib.parse import urlparse

import asyncpraw
import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

import commands
import utils
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

if "REDDIT" in config["API"]:
    reddit = asyncpraw.Reddit(
        client_id=config["API"]["REDDIT"]["CLIENT_ID"],
        client_secret=config["API"]["REDDIT"]["CLIENT_SECRET"],
        user_agent=config["API"]["REDDIT"]["USER_AGENT"],
    )


@usage("/c")
@example("/c")
@triggers(["c"])
@api_key("REDDIT")
@description("Reply to a message to search Reddit for the top comment on a URL.")
async def get_top_comment(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get the top Reddit comment for a URL.
    """

    url = utils.extract_link(update.message)
    if not url:
        await commands.usage_string(update.message, get_top_comment)
        return

    subreddit = await reddit.subreddit("all")

    if "redd.it" in url.hostname:
        # Follow redirects of shortened URLs
        url = urlparse(requests.get(url.geturl()).url)

    hostname = url.hostname.replace("www.", "")

    match hostname:
        case "reddit.com" | "redd.it" | "v.redd.it" | "old.reddit.com":
            url = url.geturl().replace("old.", "")
            submission = await reddit.submission(url=url, fetch=False)
        case "youtube.com" | "youtu.be":
            pattern = r"(?:v=|\/shorts\/|\/watch\?v=|youtu\.be\/|\/v\/|\/e\/|watch\?v%3D|watch\?feature=player_embedded&v=|%2Fvideos%2F|embed%2F|\/v\/|youtu\.be\/|\/embed\/|\/watch\?v=)([^#\&\?]*)"
            match = re.search(pattern, url.geturl())

            if not match:
                await update.message.reply_text("No comments found.")
                return

            video_id = match.group(1)

            try:
                submission = await subreddit.search(
                    f"url:{video_id}", limit=1, sort="top"
                ).__anext__()
            except StopAsyncIteration:
                await update.message.reply_text(
                    "Could not find a comment thread for this video."
                )
                return
        case _:
            try:
                submission = await subreddit.search(f'url:"{url.geturl()}"').__anext__()
            except StopAsyncIteration:
                try:
                    if url.geturl().endswith("/"):
                        submission = await subreddit.search(
                            f'url:"{url.geturl()[:-1]}"'
                        ).__anext__()
                    else:
                        submission = await subreddit.search(
                            f'url:"{url.geturl()}/"'
                        ).__anext__()
                except StopAsyncIteration:
                    await update.message.reply_text("No comments found.")
                    return

    submission.comment_sort = "top"
    submission.comment_limit = 2

    comments = await submission.comments()
    comments.replace_more(limit=0)

    comment = None

    for comment in comments:
        if comment.stickied:
            continue
        break

    if not comment:
        await update.message.reply_text("No comments found.")
        return

    await update.message.reply_text(
        f"""{escape_markdown(comment.body)}\n\n[/r/{html.escape(submission.subreddit.display_name)}](https://reddit.com{comment.permalink})""",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )
