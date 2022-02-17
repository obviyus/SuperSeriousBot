from random import choice
import praw
from prawcore.exceptions import NotFound, Forbidden, BadRequest
from configuration import config
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

reddit = praw.Reddit(
    client_id=config["REDDIT_CLIENT_ID"],
    client_secret=config["REDDIT_CLIENT_SECRET"],
    user_agent=config["REDDIT_USER_AGENT"],
)

random_posts_all = set()
random_posts_nsfw = set()


def seed(limit: int = 10, nsfw: bool = False) -> None:
    """Pre-seed the random posts cache when the bot starts"""
    logging.info("Pre-seeding random posts...")

    def runner(nsfw):
        post = reddit.random_subreddit(nsfw).random()
        while post is None or post.spoiler:
            post = reddit.random_subreddit(nsfw).random()

        return make_response(post)

    if nsfw:
        random_posts_nsfw.update(runner(nsfw) for _ in range(limit))
    else:
        random_posts_all.update(runner(nsfw) for _ in range(limit))


def make_response(post: praw.models.Submission) -> str:
    return f"{post.url}\n\n<a href='https://reddit.com{post.permalink}'>/r/{post.subreddit.display_name}</a>"


def nsfw(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random NSFW post from Reddit"""
    post = random_posts_nsfw.pop()
    update.message.reply_text(post, parse_mode="HTML")

    if len(random_posts_nsfw) < 5:
        context.dispatcher.run_async(seed, 20, True)


def randdit(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random post from a subreddit"""
    if not update.message:
        return

    subreddit: str = context.args[0] if context.args else ""

    if subreddit.startswith("r/"):
        subreddit = subreddit[2:]

    if not subreddit:
        post = random_posts_all.pop()
        update.message.reply_text(post, parse_mode="HTML")

        if len(random_posts_all) < 5:
            context.dispatcher.run_async(seed, 20, False)
    else:
        try:
            post = reddit.subreddit(subreddit).random()
            if post == None:
                # Fallback to hot post
                post = list(reddit.subreddit(subreddit).hot())
                if len(post) == 0:
                    text = f"/r/{subreddit} is empty."
                else:
                    text = (
                        make_response(choice(post))
                        + ' <span class="tg-spoiler">(subreddit does not allow random posts)</span>'
                    )
            else:
                while post.spoiler:
                    post = reddit.subreddit(subreddit).random()

                text = make_response(post)
        except (NotFound, BadRequest):
            text = "Subreddit not found or it is banned"
        except Forbidden:
            text = "Subreddit is quarantined or private"

        update.message.reply_text(text, parse_mode="HTML")
