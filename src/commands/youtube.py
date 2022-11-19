from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from commands.dl import ydl
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


async def youtube_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Join",
                    callback_data=f"yt:join,{channel_id}",
                ),
                InlineKeyboardButton(
                    "❌ Leave",
                    callback_data=f"yt:leave,{channel_id}",
                ),
            ]
        ],
    )


async def youtube_button(update: Update, _: CallbackContext) -> None:
    """Remove a user from YouTube subscriptions."""
    query = update.callback_query
    action, channel_id = query.data.replace("yt:", "").split(",")

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM youtube_subscribers
        JOIN youtube_subscriptions ON youtube_subscribers.subscription_id = youtube_subscriptions.id
        WHERE youtube_subscriptions.channel_id = ? AND user_id = ?
        """,
        (channel_id, query.from_user.id),
    )

    result = cursor.fetchone()

    cursor.execute(
        """
        SELECT * FROM youtube_subscriptions WHERE channel_id = ?
        """,
        (channel_id,),
    )
    subscription = cursor.fetchone()

    if action == "join":
        if result:
            await query.answer("You are already a part of this subscription.")
        else:
            cursor.execute(
                """
                INSERT INTO youtube_subscribers (subscription_id, user_id) VALUES (?, ?)
                """,
                (subscription["id"], query.from_user.id),
            )
            await query.answer(f"Joined subscription.")
    elif action == "leave":
        if result:
            cursor.execute(
                """
                DELETE FROM youtube_subscribers WHERE subscription_id = ? AND user_id = ?
                """,
                (subscription["id"], query.from_user.id),
            )
            await query.answer(f"Unsubscribed.")
        else:
            await query.answer("You are not a part of this group.")


def get_latest_video_id(channel_id: str) -> str:
    """Get the latest video ID from a channel."""
    metadata = ydl.extract_info(
        f"https://www.youtube.com/channel/{channel_id}",
        download=False,
    )

    return metadata["entries"][0]["entries"][0]["id"]


@usage("/yt [YOUTUBE_VIDEO_URL]")
@example("/yt https://www.youtube.com/watch?v=QH2-TGUlwu4")
@triggers(["yt"])
@description(
    "Subscribe to a YouTube channel and get notifications for new video uploads."
    "To subscribe, use /yt [YOUTUBE_VIDEO_URL] with any video from the channel."
)
async def subscribe_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Subscribe to a YouTube channel and get notifications for new video uploads.
    """
    if not context.args:
        await commands.usage_string(update.message, subscribe_youtube)
        return

    metadata = ydl.extract_info(context.args[0], download=False)
    if not metadata["channel_id"]:
        await update.message.reply_text("Invalid URL. Could not extract channel ID.")
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM youtube_subscriptions WHERE channel_id = ? AND chat_id = ?
        """,
        (metadata["channel_id"], update.message.chat.id),
    )

    result = cursor.fetchone()
    if result:
        cursor.execute(
            """
            INSERT INTO youtube_subscribers (subscription_id, user_id)
            VALUES (?, ?)
            """,
            (result["id"], update.message.from_user.id),
        )
        await update.message.reply_text(
            "This group is already subscribed to this channel. You have been added to the subscriber list."
        )
        return

    latest_video_id = get_latest_video_id(metadata["channel_id"])
    cursor.execute(
        """
        INSERT INTO youtube_subscriptions (channel_id, chat_id, creator_id, latest_video_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            metadata["channel_id"],
            update.message.chat.id,
            update.message.from_user.id,
            latest_video_id,
        ),
    )

    cursor.execute(
        """
        INSERT INTO youtube_subscribers (subscription_id, user_id)
        VALUES (?, ?)
        """,
        (cursor.lastrowid, update.message.from_user.id),
    )

    await update.message.reply_text(
        f"Successfully subscribed to <b>{metadata['channel']}</b>! You will be notified when a new video is uploaded.",
        parse_mode=ParseMode.HTML,
        reply_markup=await youtube_keyboard(metadata["channel_id"]),
    )


async def worker_youtube_subscriptions(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Worker that checks for new YouTube videos."""
    cursor = sqlite_conn.cursor()
    # TODO: Possible to avoid this subquery?
    cursor.execute(
        """
        SELECT * FROM youtube_subscriptions 
        WHERE (SELECT COUNT(*) FROM youtube_subscribers WHERE subscription_id = youtube_subscriptions.id) > 0
        """,
    )

    for subscription in cursor.fetchall():
        metadata = ydl.extract_info(
            f"https://www.youtube.com/channel/{subscription['channel_id']}",
            download=False,
        )
        latest_video_id = metadata["entries"][0]["entries"][0]["id"]

        if latest_video_id != subscription["latest_video_id"]:
            cursor.execute(
                """
                UPDATE youtube_subscriptions SET latest_video_id = ? WHERE id = ?
                """,
                (latest_video_id, subscription["id"]),
            )

            cursor.execute(
                """
                SELECT * FROM youtube_subscribers WHERE subscription_id = ?
                """,
                (subscription["id"],),
            )

            await context.bot.send_message(
                subscription["chat_id"],
                f"New video from <b>{metadata['channel']}</b>: https://www.youtube.com/watch?v={latest_video_id}"
                f"""\n\n{' '.join(
                    [f'@{await utils.get_username(subscriber["user_id"], context)}'
                     for subscriber in cursor.fetchall()])}""",
                parse_mode=ParseMode.HTML,
                reply_markup=await youtube_keyboard(subscription["channel_id"]),
            )
