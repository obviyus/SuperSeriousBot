import logging
import sqlite3
from time import sleep
from typing import TYPE_CHECKING

import requests
from praw import models
from prawcore.exceptions import NotFound, Forbidden, BadRequest, Redirect
from telegram.utils.helpers import escape_markdown
from telegram.error import Unauthorized

import configuration
from dev import reddit_increment
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

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `youtube_subscriptions` (
        `id` INTEGER PRIMARY KEY,
        `group_id` INTEGER NOT NULL,
        `channel_id` VARCHAR(255) NOT NULL,
        `channel_name` VARCHAR(255) NOT NULL,
        `author_username` VARCHAR(255) NOT NULL,
        `video_id` VARCHAR(255) NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

YOUTUBE_API_KEY = configuration.config["YOUTUBE_API_KEY"]


def make_response(post: models.Submission, username: str) -> str:
    return f"{post.url}\n\n<a href='https://reddit.com{post.permalink}'>/r/{post.subreddit.display_name};</a> @{username}"


def scan_youtube_channels(context: "telegram.ext.CallbackContext") -> None:
    """Worker function to scan dB and send posts"""
    cursor.execute(
        "SELECT `group_id`, `channel_id`, `author_username`, `video_id` FROM `youtube_subscriptions`"
    )

    def scanner(
        each_group_id: str,
        each_channel_id: str,
        each_author_username: str,
        old_video_id,
    ) -> None:
        YOUTUBE_LATEST_VIDEO_ENDPOINT = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={each_channel_id}&part=snippet,id&order=date&maxResults=1"

        latest_video_id = requests.get(YOUTUBE_LATEST_VIDEO_ENDPOINT).json()["items"][
            0
        ]["id"]["videoId"]

        if latest_video_id != old_video_id:
            context.bot.send_message(
                chat_id=each_group_id,
                text=f"https://www.youtube.com/watch?v={latest_video_id}; @{each_author_username}",
                parse_mode="HTML",
            )

            cursor.execute(
                "UPDATE `youtube_subscriptions` SET `video_id` = ? WHERE `group_id` = ? AND `channel_id` = ?",
                (latest_video_id, each_group_id, each_channel_id),
            )
            conn.commit()

    for group_id, channel_id, author_username, video_id in cursor.fetchall():
        context.dispatcher.run_async(
            scanner, group_id, channel_id, author_username, video_id
        )


def deliver_reddit_subscriptions(context: "telegram.ext.CallbackContext") -> None:
    """Worker function to scan dB and send posts"""
    cursor.execute(
        "SELECT `group_id`, `subreddit_name`, `author_username` FROM `reddit_subscriptions`"
    )

    def poster(each_group_id: str, each_author_username: str, name: str) -> None:
        try:
            for post in reddit.subreddit(name).hot(limit=3):
                if post.stickied:
                    continue

                context.bot.send_message(
                    chat_id=each_group_id,
                    text=make_response(post, each_author_username),
                    parse_mode="html",
                )
                break
        except (NotFound, BadRequest, Redirect, Forbidden, Unauthorized):
            cursor.execute(
                "DELETE `author_username` FROM `reddit_subscriptions` WHERE `subreddit_name` = ? AND `group_id` = ?",
                (subreddit_name, each_group_id),
            )
            conn.commit()

            context.bot.send_message(
                chat_id=each_group_id,
                text=f"@{each_author_username} error occurred while fetching posts from /r/{name}. Automatically "
                f"removing subscription.",
                parse_mode="html",
            )

    for group_id, subreddit_name, author_username in cursor.fetchall():
        context.dispatcher.run_async(poster, group_id, author_username, subreddit_name)

        reddit_increment(subreddit_name)
        sleep(1)


def list_reddit_subscriptions(
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


def list_youtube_subscriptions(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Get a list of all YouTube channels group is subscribed to"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    cursor.execute(
        "SELECT `channel_name`, `author_username` FROM `youtube_subscriptions` WHERE `group_id` = ?",
        (message.chat.id,),
    )

    rows = cursor.fetchall()
    if not rows:
        message.reply_text("No YouTube channels subscribed.")
        return

    text = f"<b>YouTube subscriptions for {update.effective_chat.title}</b>\n"

    # Group YouTube channel names for the same user
    grouped_rows: dict = {}
    for channel_names, author_username in rows:
        if author_username not in grouped_rows:
            grouped_rows[author_username] = []
        grouped_rows[author_username].append(channel_names)

    for author_username, subreddit_names in grouped_rows.items():
        text += f"\n<b><a href='https://t.me/{author_username}'>@{author_username}</a></b>\n"
        for channel_names in subreddit_names:
            text += f"<code>- {channel_names}</code>\n"

    text = text + f"\nSubscribed to {len(rows)} channel(s)."

    message.reply_text(
        text,
        parse_mode="HTML",
        disable_notification=True,
        disable_web_page_preview=True,
    )


def unsubscribe_reddit(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Removes a subreddit from group's subscriptions"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    if not context.args:
        message.reply_text(
            "*Usage:*\n`/unsubscribe {SUBREDDIT_NAME}`\n`/unsubscribe yt {CHANNEL_NAME}`\n\n"
            "*Example:*\n`/unsubscribe France`\n`/unsubscribe yt LinusTechTips`"
        )
        return
    else:
        subreddit: str = context.args[0]
        if subreddit.startswith("r/"):
            subreddit = subreddit[2:].lower()

        cursor.execute(
            "SELECT `author_username` FROM `reddit_subscriptions` WHERE `subreddit_name` = ? COLLATE NOCASE AND `group_id` = ?",
            (subreddit, message.chat.id),
        )

        logging.getLogger().testing("group_id: {}".format(message.chat.id))
        logging.getLogger().testing("subreddit: {}".format(subreddit))

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
            "DELETE FROM `reddit_subscriptions` WHERE `subreddit_name` = ? COLLATE NOCASE AND `group_id` = ?",
            (subreddit, message.chat.id),
        )
        conn.commit()

        message.reply_text(
            f"Unsubscribed from /r/{escape_markdown(subreddit)} by @{escape_markdown(message.from_user.username)}.",
            disable_notification=True,
        )


def unsubscribe_youtube(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Removes a YouTube channel from group's subscriptions"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    if not context.args:
        message.reply_text(
            "*Usage:*\n`/unsubscribe {SUBREDDIT_NAME}`\n`/unsubscribe yt {CHANNEL_NAME}`\n\n"
            "*Example:*\n`/unsubscribe France`\n`/unsubscribe yt LinusTechTips`"
        )
        return
    else:
        subreddit: str = " ".join(context.args).lower()

        cursor.execute(
            "SELECT `author_username` FROM `youtube_subscriptions` WHERE `channel_name` = ? COLLATE NOCASE AND `group_id` = ?",
            (subreddit, message.chat.id),
        )

        logging.getLogger().testing("group_id: {}".format(message.chat.id))
        logging.getLogger().testing("subreddit: {}".format(subreddit))

        result = cursor.fetchone()
        if not result:
            message.reply_text(
                f"Not subscribed to {escape_markdown(subreddit)} in this group."
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
            "DELETE FROM `youtube_subscriptions` WHERE `channel_name` = ? COLLATE NOCASE AND `group_id` = ?",
            (subreddit, message.chat.id),
        )
        conn.commit()

        message.reply_text(
            f"Unsubscribed from {escape_markdown(subreddit)} by @{escape_markdown(message.from_user.username)}.",
            disable_notification=True,
        )


def subscribe_reddit(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Subscribe to a subreddit and get the hot post day at 9AM and 9PM."""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    if not context.args:
        message.reply_text(
            "*Usage:*\n`/subscribe {SUBREDDIT_NAME}`\n`/subscribe yt {CHANNEL_NAME}`\n\n"
            "*Example:*\n`/subscribe France`\n`/subscribe yt LinusTechTips`"
        )
        return
    else:
        subreddit: str = context.args[0]
        if subreddit.startswith("r/"):
            subreddit = subreddit[2:]
        subreddit = subreddit.lower()

        cursor.execute(
            "SELECT `author_username` FROM `reddit_subscriptions` WHERE `subreddit_name` = ? COLLATE NOCASE AND `group_id` = ?",
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


def subscribe_youtube(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Subscribe to a YouTube and get their videos delivered."""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    if not context.args:
        message.reply_text(
            "*Usage:*\n`/subscribe {SUBREDDIT_NAME}`\n`/subscribe yt {CHANNEL_NAME}`\n\n"
            "*Example:*\n`/subscribe France`\n`/subscribe yt LinusTechTips`"
        )
        return
    else:
        channel_name: str = " ".join(context.args).lower()

        cursor.execute(
            "SELECT `author_username` FROM `youtube_subscriptions` WHERE `channel_name` = ? COLLATE NOCASE AND `group_id` = ?",
            (channel_name, message.chat.id),
        )

        result = cursor.fetchone()
        if result:
            message.reply_text(
                f"Already subscribed to {escape_markdown(channel_name)} in this group by @{escape_markdown(result[2])}."
            )
            return

        YOUTUBE_API_ENDPOINT = f"https://www.googleapis.com/youtube/v3/search?part=snippet,id&type=channel&maxResults=1&&key={YOUTUBE_API_KEY}"
        response = requests.get(YOUTUBE_API_ENDPOINT, params={"q": channel_name}).json()

        if response["pageInfo"]["totalResults"] == 0:
            message.reply_text(text="Channel not found.")
            return

        channel_id = response["items"][0]["id"]["channelId"]
        channel_name = response["items"][0]["snippet"]["title"]

        cursor.execute(
            "INSERT INTO `youtube_subscriptions` (`group_id`, `channel_name`, `channel_id`, `author_username`) VALUES (?, ?, ?, ?)",
            (message.chat.id, channel_name, channel_id, message.from_user.username),
        )
        conn.commit()

        message.reply_text(
            f"Subscribed to {escape_markdown(channel_name)} by @{escape_markdown(message.from_user.username)}."
        )
