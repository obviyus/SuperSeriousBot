from typing import TYPE_CHECKING

import praw
import prawcore
from telegram import MessageEntity

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

reddit = praw.Reddit(
    client_id=config["REDDIT_CLIENT_ID"],
    client_secret=config["REDDIT_CLIENT_SECRET"],
    user_agent=config["REDDIT_USER_AGENT"],
)


def comment(
    update: "telegram.Update", _context: "telegram.ext.CallbackContext"
) -> None:
    """Replies to a link with the top comment posted on Reddit"""
    message: "telegram.Message"
    if update.message.reply_to_message:
        message = update.message.reply_to_message
    elif update.message:
        message = update.message
    else:
        return

    entities: list = list(message.parse_entities([MessageEntity.URL]).values())
    original_url = entities[0]
    post: praw.models.Submission

    try:
        post = reddit.submission(url=original_url)
    except praw.exceptions.InvalidURL:
        for submission in reddit.subreddit("all").search(
            f"url:{original_url}", sort="top", limit=1
        ):
            post = submission
            break

    try:
        post.comments.replace_more(limit=0)
        post.comment_sort = "top"
        top_comment: praw.models.Comment = post.comments[0]

        comment_body = top_comment.body
        if len(comment_body) > 500:
            comment_body = comment_body[:500] + "..."

        text = f"{comment_body} (<a href='https://reddit.com{top_comment.permalink}'>/u/{top_comment.author.name})</a>"
        message.reply_text(text=text, parse_mode="html", disable_web_page_preview=True)
    except prawcore.exceptions.NotFound:
        message.reply_text(text="No comments found.")
