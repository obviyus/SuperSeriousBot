import html
from urllib.parse import parse_qs

import asyncpraw
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config.options import config

if "REDDIT" in config["API"]:
    reddit = asyncpraw.Reddit(
        client_id=config["API"]["REDDIT"]["CLIENT_ID"],
        client_secret=config["API"]["REDDIT"]["CLIENT_SECRET"],
        user_agent=config["API"]["REDDIT"]["USER_AGENT"],
    )


async def get_top_comment(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get the top Reddit comment for a URL.
    """

    url = utils.extract_link(update)
    if not url:
        await utils.usage_string(update.message)
        return

    subreddit = await reddit.subreddit("all")

    hostname = url.hostname.replace("www.", "")

    match hostname:
        case ("reddit.com" | "redd.it"):
            submission = await reddit.submission(url=url.geturl(), fetch=False)
        case ("youtube.com" | "youtu.be"):
            video_id = parse_qs(url.query)["v"][0]
            submission = await subreddit.search(
                f"url:{video_id}", limit=1, sort="top"
            ).__anext__()
        case _:
            try:
                submission = await subreddit.search(f'url:"{url}"').__anext__()
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
        f"""{html.escape(comment.body)}\n\n<a href='https://reddit.com{comment.permalink}'>/r/{html.escape(submission.subreddit.display_name)}</a>""",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
