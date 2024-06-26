import asyncio
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from commands.dl import ydl
from config.db import get_db
from utils.decorators import description, example, triggers, usage


async def youtube_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Join", callback_data=f"yt:join,{channel_id}"),
                InlineKeyboardButton(
                    "❌ Leave", callback_data=f"yt:leave,{channel_id}"
                ),
            ]
        ]
    )


async def youtube_button(update: Update, _: CallbackContext) -> None:
    query = update.callback_query
    action, channel_id = query.data.replace("yt:", "").split(",")
    user_id = query.from_user.id

    async with get_db(write=True) as conn:
        async with conn.execute(
            """
            SELECT s.id FROM youtube_subscriptions s
            LEFT JOIN youtube_subscribers sub ON s.id = sub.subscription_id
            WHERE s.channel_id = ? AND (sub.user_id = ? OR sub.user_id IS NULL)
            """,
            (channel_id, user_id),
        ) as cursor:
            result = await cursor.fetchone()

        if action == "join":
            if result and result[1]:
                await query.answer("You are already a part of this subscription.")
            else:
                await conn.execute(
                    "INSERT OR IGNORE INTO youtube_subscribers (subscription_id, user_id) VALUES (?, ?)",
                    (result[0], user_id),
                )
                await query.answer("Joined subscription.")
        elif action == "leave":
            if result and result[1]:
                await conn.execute(
                    "DELETE FROM youtube_subscribers WHERE subscription_id = ? AND user_id = ?",
                    (result[0], user_id),
                )
                await query.answer("Unsubscribed.")
            else:
                await query.answer("You are not a part of this group.")
        conn.commit()


async def extract_info(url: str, download: bool = False):
    return await asyncio.to_thread(ydl.extract_info, url, download=download)


async def get_latest_video_id(channel_id: str) -> str:
    metadata = await extract_info(f"https://www.youtube.com/channel/{channel_id}")
    return metadata["entries"][0]["entries"][0]["id"]


async def get_latest_videos(channel_id: str, max_videos: int = 5) -> list:
    metadata = await extract_info(f"https://www.youtube.com/channel/{channel_id}")
    return [video["id"] for video in metadata["entries"][0]["entries"][:max_videos]]


@usage("/yt [YOUTUBE_VIDEO_URL]")
@example("/yt https://www.youtube.com/watch?v=QH2-TGUlwu4")
@triggers(["yt"])
@description(
    "Subscribe to a YouTube channel and get notifications for new video uploads. "
    "To subscribe, use /yt [YOUTUBE_VIDEO_URL] with any video from the channel."
)
async def subscribe_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await commands.usage_string(update.message, subscribe_youtube)
        return

    metadata = await extract_info(context.args[0])
    if not metadata.get("channel_id"):
        await update.message.reply_text("Invalid URL. Could not extract channel ID.")
        return

    async with get_db(write=True) as conn:
        async with conn.execute(
            "SELECT id FROM youtube_subscriptions WHERE channel_id = ? AND chat_id = ?",
            (metadata["channel_id"], update.message.chat.id),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            await conn.execute(
                "INSERT OR IGNORE INTO youtube_subscribers (subscription_id, user_id) VALUES (?, ?)",
                (result[0], update.message.from_user.id),
            )
            await conn.commit()
            await update.message.reply_text(
                "This group is already subscribed to this channel. You have been added to the subscriber list."
            )
            return

        latest_video_id = await get_latest_video_id(metadata["channel_id"])
        await conn.execute(
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
        subscription_id = conn.last_insert_rowid()

        await conn.execute(
            "INSERT INTO youtube_subscribers (subscription_id, user_id) VALUES (?, ?)",
            (subscription_id, update.message.from_user.id),
        )
        await conn.commit()

    await update.message.reply_text(
        f"Successfully subscribed to <b>{metadata['channel']}</b>! You will be notified when a new video is uploaded.",
        parse_mode=ParseMode.HTML,
        reply_markup=await youtube_keyboard(metadata["channel_id"]),
    )


async def update_video_history(conn, subscription_id: int, video_id: str, status: str):
    await conn.execute(
        """
        INSERT INTO video_history (subscription_id, video_id, status, create_time)
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO NOTHING;
        """,
        (subscription_id, video_id, status, datetime.now().isoformat()),
    )
    await conn.commit()


async def get_video_history(conn, subscription_id: int) -> dict:
    async with conn.execute(
        """
        SELECT video_id, status, create_time FROM video_history
        WHERE subscription_id = ?
        """,
        (subscription_id,),
    ) as cursor:
        results = await cursor.fetchall()
    return {
        row["video_id"]: {"status": row["status"], "create_time": row["create_time"]}
        for row in results
    }


async def worker_youtube_subscriptions(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_db(write=True) as conn:
        async with conn.execute(
            """
            SELECT s.*, COUNT(sub.user_id) as subscriber_count 
            FROM youtube_subscriptions s
            JOIN youtube_subscribers sub ON s.id = sub.subscription_id
            GROUP BY s.id
            HAVING subscriber_count > 0
            """
        ) as cursor:
            subscriptions = await cursor.fetchall()

        for subscription in subscriptions:
            try:
                latest_videos = await get_latest_videos(subscription["channel_id"])
                video_history = await get_video_history(conn, subscription["id"])

                for video_id in latest_videos:
                    if video_id not in video_history or (
                        video_history[video_id]["status"] == "error"
                        and datetime.fromisoformat(
                            video_history[video_id]["create_time"]
                        )
                        < datetime.now() - timedelta(hours=24)
                    ):
                        try:
                            video_details = await extract_info(
                                f"https://www.youtube.com/watch?v={video_id}"
                            )

                            if video_id != subscription["latest_video_id"]:
                                await conn.execute(
                                    "UPDATE youtube_subscriptions SET latest_video_id = ? WHERE id = ?",
                                    (video_id, subscription["id"]),
                                )

                                async with conn.execute(
                                    "SELECT user_id FROM youtube_subscribers WHERE subscription_id = ?",
                                    (subscription["id"],),
                                ) as cursor:
                                    subscribers = await cursor.fetchall()

                                mention_list = " ".join(
                                    [
                                        f'@{await utils.get_username(sub["user_id"], context)}'
                                        for sub in subscribers
                                    ]
                                )

                                await context.bot.send_message(
                                    subscription["chat_id"],
                                    f"New video from <b>{video_details['channel']}</b>: https://www.youtube.com/watch?v={video_id}"
                                    f"\n\n{mention_list}",
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=await youtube_keyboard(
                                        subscription["channel_id"]
                                    ),
                                )

                            await update_video_history(
                                conn, subscription["id"], video_id, "success"
                            )
                            await conn.commit()

                        except Exception as e:
                            print(f"Error processing video {video_id}: {str(e)}")
                            await update_video_history(
                                conn, subscription["id"], video_id, "error"
                            )
                            await conn.commit()

            except Exception as e:
                print(f"Error processing subscription {subscription['id']}: {str(e)}")
