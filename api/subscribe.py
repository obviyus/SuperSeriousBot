import sqlite3
from time import sleep
from typing import TYPE_CHECKING

import praw
from prawcore.exceptions import NotFound, Forbidden, BadRequest, Redirect
from telegram.utils.helpers import escape_markdown

from .randdit import reddit

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

    def poster(group_id: str, author_username: str, name: str) -> None:
        try:
            for post in reddit.subreddit(name).hot(limit=3):
                if post.stickied:
                    continue

                context.bot.send_message(
                    chat_id=group_id,
                    text=make_response(post, author_username),
                    parse_mode="html",
                )
                break
        except (NotFound, BadRequest, Redirect, Forbidden):
            cursor.execute(
                "SELECT `author_username` FROM `reddit_subscriptions` WHERE `subreddit_name` = ? AND `group_id` = ?",
                (subreddit_name, group_id),
            )
            conn.commit()

            context.bot.send_message(
                chat_id=group_id,
                text=f"@{author_username} error occurred while fetching posts from /r/{name}. Automatically removing subscription.",
                parse_mode="html",
            )

    for group_id, subreddit_name, author_username in cursor.fetchall():
        context.dispatcher.run_async(poster, group_id, author_username, subreddit_name)
        sleep(1)


def list_subscriptions(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Get a list of all subreddits group is subscribed to"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    cursor.execute(
        "SELECT `subreddit_name`, `author_username` FROM `reddit_subscriptions` WHERE `group_id` = ?",
        (message.chat.id,),
    )

    rows = cursor.fetchall()
    if not rows:
        message.reply_text("No subreddits subscribed to.")
        return

    text = f"<b>Reddit subscriptions for {update.effective_chat.title}</b>\n"

    # Group subreddit names for the same user
    grouped_rows: dict = {}
    for subreddit_name, author_username in rows:
        if author_username not in grouped_rows:
            grouped_rows[author_username] = []
        grouped_rows[author_username].append(subreddit_name)

    for author_username, subreddit_names in grouped_rows.items():
        text += f"\n<b><a href='https://t.me/{author_username}'>@{author_username}</a></b>\n"
        for subreddit_name in subreddit_names:
            text += f"<code>- /r/{subreddit_name}</code>\n"

    text = text + f"\nSubscribed to {len(rows)} subreddit(s)."

    message.reply_text(
        text,
        parse_mode="HTML",
        disable_notification=True,
        disable_web_page_preview=True,
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
            message.reply_text(
                f"Not subscribed to /r/{escape_markdown(subreddit)} in this group."
            )
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
            f"Unsubscribed from /r/{escape_markdown(subreddit)} by @{escape_markdown(message.from_user.username)}.",
            disable_notification=True,
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
                f"Already subscribed to /r/{escape_markdown(subreddit)} in this group by @{escape_markdown(result[2])}."
            )
            return

        try:
            for post in reddit.subreddit(subreddit).hot(limit=3):
                subreddit = post.subreddit.display_name

            cursor.execute(
                "INSERT INTO `reddit_subscriptions` (`group_id`, `subreddit_name`, `author_username`) VALUES (?, ?, ?)",
                (message.chat.id, subreddit, message.from_user.username),
            )
            conn.commit()

            message.reply_text(
                f"Subscribed to /r/{escape_markdown(subreddit)} by @{escape_markdown(message.from_user.username)}."
            )
        except (NotFound, BadRequest, Redirect):
            message.reply_text(text="Subreddit not found or banned")
        except Forbidden:
            message.reply_text(text="Subreddit is quarantined or private")
