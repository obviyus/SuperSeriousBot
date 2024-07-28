import asyncio
import logging
from random import choice

from asyncpraw import models
from asyncprawcore.exceptions import (
    BadRequest,
    Forbidden,
    NotFound,
    UnavailableForLegalReasons,
)
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import logger
from utils.decorators import api_key, description, example, triggers, usage
from .reddit_comment import reddit

random_posts_all = set()
random_posts_nsfw = set()


async def worker_seed_posts(context: ContextTypes.DEFAULT_TYPE, limit=10) -> None:
    """Pre-seed the random posts cache when the bot starts"""
    logging.info("Pre-seeding 10 random posts...")

    async def runner(is_nsfw = False):
        try:
            post = await (await reddit.random_subreddit(is_nsfw)).random()
            while post is None or post.spoiler:
                post = await (await reddit.random_subreddit(is_nsfw)).random()
        except UnavailableForLegalReasons:
            return

        logger.info("Seeding post: %s", post.url)
        if is_nsfw:
            random_posts_nsfw.add(make_response(post))
        else:
            random_posts_all.add(make_response(post))

    tasks = []
    for _ in range(limit):
        tasks.append(asyncio.ensure_future(runner()))

    await asyncio.gather(*tasks)


def make_response(post: models.Submission, username=None) -> str:
    return (
        f"<b>{post.title}</b>"
        f"\n\n{post.url}"
        f"\n\n<a href='https://reddit.com{post.permalink}'>/r/{post.subreddit.display_name}</a>"
        f"\n\n{'@' + username if username else ''}"
    )


@example("/r")
@triggers(["r"])
@api_key("REDDIT")
@usage("/r [subreddit (optional)]")
@description("Get a random post from Reddit. Optionally specify the subreddit.")
async def randdit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random post from a subreddit"""
    subreddit: str = context.args[0] if context.args else ""

    if subreddit.startswith("r/"):
        subreddit = subreddit[2:]

    if not subreddit:
        if len(random_posts_all) < 5:
            context.job_queue.run_once(worker_seed_posts, 0)
            await worker_seed_posts(context, 2)

        await update.message.reply_text(
            random_posts_all.pop(), parse_mode=ParseMode.HTML
        )
    else:
        try:
            post = await (await reddit.subreddit(subreddit)).random()
            if not post:
                # Fallback to hot post
                hot_posts = (await reddit.subreddit(subreddit)).hot(limit=3)
                posts = [post async for post in hot_posts if not post.spoiler]

                if len(posts) == 0:
                    text = f"/r/{subreddit} is empty."
                else:
                    text = (
                        make_response(choice(posts))
                        + '\n<span class="tg-spoiler">(subreddit does not allow random posts)</span>'
                    )
            else:
                while post.spoiler:
                    post = await (await reddit.subreddit(subreddit)).random()

                text = make_response(post)
        except (NotFound, BadRequest):
            text = "Subreddit not found or it is banned."
        except Forbidden:
            text = "Subreddit is quarantined or private."

        await update.message.reply_text(text, ParseMode.HTML)
