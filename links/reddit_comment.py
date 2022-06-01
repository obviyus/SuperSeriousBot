import logging
from typing import TYPE_CHECKING
from telegram.utils.helpers import escape_markdown
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
        logging.getLogger().testing("Post: {}".format(post.permalink))
    except (praw.exceptions.InvalidURL, prawcore.exceptions.NotFound):
        for submission in reddit.subreddit("all").search(
            f"url:{original_url}",
            sort="top",
        ):
            post = submission
            break
        logging.getLogger().testing("Post: {}".format(post.permalink))
    try:
        logging.getLogger().testing("Post: {}".format(post.permalink))
        post.comment_sort = "top"
        post.comments.replace_more(limit=0)
        for comment in post.comments:
            if comment.stickied:
                continue
            top_comment = comment
            break

        if not top_comment:
            raise prawcore.exceptions.NotFound

        comment_body = top_comment.body
        if len(comment_body) > 500:
            comment_body = escape_markdown(comment_body[:500]) + "..."

        logging.getLogger().testing("Post: {}".format(post.permalink))

        try:
            text = f"{comment_body}\n\n [/u/{top_comment.author.name}](https://reddit.com{top_comment.permalink})"
        except AttributeError:
            text = f"{comment_body}\n\n [/u/deleted]({escape_markdown(f'https://reddit.com{top_comment.permalink}')})"

        message.reply_text(
            text=text, parse_mode="markdown", disable_web_page_preview=True
        )
    except UnboundLocalError:
        message.reply_text(text="URL not found on Reddit.")
    except prawcore.exceptions.NotFound:
        message.reply_text(text="No comments found.")