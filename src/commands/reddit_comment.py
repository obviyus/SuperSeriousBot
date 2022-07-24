import html

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


async def get_top_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get the top Reddit comment for a URL.
    """

    url = utils.extract_link(update)
    if not url:
        await utils.usage_string(update.message)
        return

    if "reddit.com" in url or "redd.it" in url:
        submission = await reddit.submission(url=url)
    else:
        subreddit = await reddit.subreddit("all")
        try:
            submission = await subreddit.search(f'url:"{url}"').__anext__()
        except StopAsyncIteration:
            await update.message.reply_text("No comments found.")
            return

        await submission.load()

    comment = submission.comments[0]
    await update.message.reply_text(
        f"""{html.escape(comment.body)}""",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
