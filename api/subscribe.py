from prawcore.exceptions import NotFound, Forbidden, BadRequest
from time import sleep
from typing import TYPE_CHECKING
import praw
from .randdit import reddit
import sqlite3

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect("/db/groups.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `reddit_subscriptions` (
        `id` INTEGER PRIMARY KEY,
        `group_id` INTEGER NOT NULL,
        `subreddit_name` VARCHAR(255) NOT NULL,
        `author_username` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)


def make_response(post: praw.models.Submission, username: str) -> str:
    return f"{post.url}\n\n<a href='https://reddit.com{post.permalink}'>/r/{post.subreddit.display_name}; @{username}</a>"


def deliver_reddit_subscriptions(context: "telegram.ext.CallbackContext") -> None:
    """Worker function to scan dB and send posts"""
    cursor.execute(
        "SELECT `group_id`, `subreddit_name`, `author_username` FROM `reddit_subscriptions`"
    )

    for group_id, subreddit_name, author_username in cursor.fetchall():
        for post in reddit.subreddit(subreddit_name).hot(limit=3):
            if post.stickied:
                continue

            context.bot.send_message(
                chat_id=group_id,
                text=make_response(post, author_username),
                parse_mode="html",
            )
            sleep(1)


def list(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a list of all subreddits group is subscribed to"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    cursor.execute(
        "SELECT `subreddit_name`, `author_username` FROM `reddit_subscriptions` WHERE `group_id` = ?",
        (message.chat.id,),
    )

    result = cursor.fetchall()
    if not result:
        message.reply_text("No subreddits subscribed to.")
        return

    message.reply_text(
        "Subscribed to:\n"
        + "\n".join(f"/r/{subreddit} by @{username}" for subreddit, username in result)
        + "\n"
    )


def unsubscribe(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Removes a subreddit from group's subscriptions"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    if not context.args:
        message.reply_text(
            "*Usage:* `/unsubscribe {SUBREDDIT_NAME}`\n"
            "*Example:* `/unsubscribe France`\n"
        )
        return
    else:
        subreddit: str = context.args[0]
        if subreddit.startswith("r/"):
            subreddit = subreddit[2:].lower()

        cursor.execute(
            "SELECT `author_username` FROM `reddit_subscriptions` WHERE `subreddit_name` = ? AND `group_id` = ?",
            (subreddit, message.chat.id),
        )
        result = cursor.fetchone()
        if not result:
            message.reply_text(f"Not subscribed to /r/{subreddit} in this group.")
            return

        user: telegram.ChatMember = context.bot.get_chat_member(
            message.chat.id, message.from_user.id
        )

        if (
            result[0] != message.from_user.username
            and user["status"] == telegram.constants.CHATMEMBER_MEMBER
        ):
            message.reply_text(
                "Only admins or the user who subscribed can unsubscribe."
            )
            return

        cursor.execute(
            "DELETE FROM `reddit_subscriptions` WHERE `subreddit_name` = ? AND `group_id` = ?",
            (subreddit, message.chat.id),
        )
        conn.commit()

        message.reply_text(
            f"Unsubscribed from /r/{subreddit} by @{message.from_user.username}."
        )


def subscribe(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Subscribe to a subreddit and get the hot post day at 9AM and 9PM."""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    if not context.args:
        message.reply_text(
            "*Usage:* `/subscribe {SUBREDDIT_NAME}`\n"
            "*Example:* `/subscribe France`\n"
        )
        return
    else:
        subreddit: str = context.args[0]
        if subreddit.startswith("r/"):
            subreddit = subreddit[2:]
        subreddit = subreddit.lower()

        cursor.execute(
            "SELECT `author_username` FROM `reddit_subscriptions` WHERE `subreddit_name` = ? AND `group_id` = ?",
            (subreddit, message.chat.id),
        )
        result = cursor.fetchone()
        if result:
            message.reply_text(
                f"Already subscribed to /r/{subreddit} in this group by @{result[2]}."
            )
            return

        try:
            reddit.subreddit(subreddit).hot(limit=1)
            cursor.execute(
                "INSERT INTO `reddit_subscriptions` (`group_id`, `subreddit_name`, `author_username`) VALUES (?, ?, ?)",
                (message.chat.id, subreddit, message.from_user.username),
            )
            conn.commit()
            message.reply_text(
                f"Subscribed to /r/{subreddit} by @{message.from_user.username}."
            )
        except (NotFound, BadRequest):
            text = "Subreddit not found or it is banned"
        except Forbidden:
            text = "Subreddit is quarantined or private"
