import praw
from prawcore.exceptions import NotFound, Forbidden, BadRequest
from configuration import config

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

reddit = praw.Reddit(
    client_id=config["REDDIT_CLIENT_ID"],
    client_secret=config["REDDIT_CLIENT_SECRET"],
    user_agent=config["REDDIT_USER_AGENT"],
)


def randdit(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random post from a subreddit"""
    if not update.message:
        return

    subreddit: str = context.args[0] if context.args else ""

    if subreddit.startswith("r/"):
        subreddit = subreddit[2:]

    if not subreddit:
        post = reddit.random_subreddit(nsfw=True).random()
        while post is None or post.spoiler:
            post = reddit.random_subreddit(nsfw=True).random()

        text = post.url
    else:
        try:
            post = reddit.subreddit(subreddit).random()
            if post == None:
                text = "Subreddit does not allow random posts"
            else:
                while post.spoiler:
                    post = post.subreddit.random()

                text = post.url
        except (NotFound, BadRequest):
            text = "Subreddit not found or it is banned"
        except Forbidden:
            text = "Subreddit is quarantined or private"

    update.message.reply_text(text, parse_mode="HTML")
