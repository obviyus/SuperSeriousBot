import asyncio
import logging
from random import choice
from time import sleep

import asyncpraw
from asyncprawcore.exceptions import BadRequest, Forbidden, NotFound
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .reddit_comment import reddit

random_posts_all = set()
random_posts_nsfw = set()


async def worker_seed_posts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pre-seed the random posts cache when the bot starts"""
    logging.info("Pre-seeding 10 random posts...")
    limit = 10

    async def runner(is_nsfw):
        post = await (await reddit.random_subreddit(is_nsfw)).random()
        while post is None or post.spoiler:
            post = await (await reddit.random_subreddit(is_nsfw)).random()

        sleep(1)
        if is_nsfw:
            random_posts_nsfw.add(make_response(post))
        else:
            random_posts_all.add(make_response(post))

    # Run the worker in a loop asynchronously
    nsfw_coros = [runner(True) for _ in range(limit)]
    all_coros = [runner(False) for _ in range(limit)]

    await asyncio.gather(*nsfw_coros, *all_coros)


def make_response(post: asyncpraw.models.Submission) -> str:
    return f"{post.url}\n\n<a href='https://reddit.com{post.permalink}'>/r/{post.subreddit.display_name}</a>"


async def nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random NSFW post from Reddit"""
    await update.message.reply_text(random_posts_nsfw.pop(), parse_mode=ParseMode.HTML)

    if len(random_posts_nsfw) < 5:
        context.job_queue.run_once(worker_seed_posts, 0)


async def randdit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random post from a subreddit"""
    subreddit: str = context.args[0] if context.args else ""

    if subreddit.startswith("r/"):
        subreddit = subreddit[2:]

    if not subreddit:
        await update.message.reply_text(
            random_posts_all.pop(), parse_mode=ParseMode.HTML
        )

        if len(random_posts_all) < 5:
            context.job_queue.run_once(worker_seed_posts, 0)
    else:
        try:
            post = await (await reddit.subreddit(subreddit)).random()
            if not post:
                # Fallback to hot post
                posts = list(reddit.subreddit(subreddit).hot(limit=5))
                post = choice(posts)

                if len(posts) == 0:
                    text = f"/r/{subreddit} is empty."
                else:
                    text = (
                        make_response(post)
                        + '\n<span class="tg-spoiler">(subreddit does not allow random posts)</span>'
                    )
            else:
                while post.spoiler:
                    post = (await reddit.subreddit(subreddit)).random()

                text = make_response(post)
        except (NotFound, BadRequest):
            text = "Subreddit not found or it is banned."
        except Forbidden:
            text = "Subreddit is quarantined or private."

        await update.message.reply_text(text, ParseMode.HTML)
