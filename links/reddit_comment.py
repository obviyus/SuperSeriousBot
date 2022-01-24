from typing import TYPE_CHECKING
from telegram import MessageEntity
from configuration import config
import praw

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

    for submission in reddit.subreddit("all").search(
        f'url:"{original_url}"',
        sort="top",
    ):
        submission.comments.replace_more(limit=0)
        for top_level_comment in submission.comments:
            if top_level_comment.stickied:
                continue

            text = f"{top_level_comment.body}\n\n<a href='https://reddit.com{top_level_comment.permalink}'>- {top_level_comment.author.name}</a>"
            message.reply_text(
                text=text, parse_mode="html", disable_web_page_preview=True
            )
            return
