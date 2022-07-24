from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils.string
from config.db import redis, sqlite_conn
from utils import readable_time, usage_string


async def increment(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Increment message count for a user. Also store last seen time in Redis.
    """
    if not update.message:
        return

    chat_id = update.message.chat.id
    user_object = update.message.from_user

    # Set last seen time in Redis
    redis.set(
        f"seen:{user_object.username}",
        round(datetime.now().timestamp()),
    )

    # Update user_id vs. username in Redis
    redis.set(
        f"user_id:{user_object.id}", user_object.username or user_object.first_name
    )

    cursor = sqlite_conn.cursor()
    cursor.execute(
        f"INSERT INTO chat_stats (chat_id, user_id) VALUES (?, ?)",
        (chat_id, user_object.id),
    )


async def get_last_seen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get time of last message of a user.
    """
    if not context.args:
        await usage_string(update.message)
        return

    username = context.args[0].split("@")[1]

    # Get last seen time in Redis
    last_seen = redis.get(f"seen:{username}")
    if not last_seen:
        await update.message.reply_text(f"@{username} has never been seen.")
        return

    last_seen = int(last_seen)
    await update.message.reply_text(
        f"<a href='https://t.me/{username}'>@{username}</a>'s last message was {await readable_time(last_seen)} ago.",
        disable_web_page_preview=True,
        disable_notification=True,
        parse_mode=ParseMode.HTML,
    )


async def get_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get message count by user for the last day.
    """
    chat_id = update.message.chat_id
    user_object = update.message.from_user

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """SELECT *, COUNT(user_id) 
        FROM chat_stats 
        WHERE chat_id = ? AND 
        create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime')
        GROUP BY user_id
        ORDER BY COUNT(user_id) DESC
        LIMIT 10;
        """,
        (chat_id,),
    )

    users = cursor.fetchall()

    if not users:
        await update.message.reply_text("No messages recorded.")
        return

    text = f"Stats for <b>{update.message.chat.title}:</b>\n\n"

    # TODO: Use a NamedTuple for cleaner code
    total_count = sum(user[4] for user in users)

    # Ignore special case for user
    if user_object.id == 1060827049:
        text += f"<code>100% degen - {await utils.string.get_username(user_object.id, context)}</code>\n"

    for _, _, timestamp, user_id, count in users:
        percent = round(count / total_count * 100, 2)
        text += f"""<code>{percent if percent > 10 else f" {percent}"}% - {await utils.string.get_username(user_id, context)}</code>\n"""

    text += f"\nTotal messages: <b>{total_count}</b>"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


async def get_total_chat_stats(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Get total message count for all users.
    """
    chat_id = update.message.chat_id
    user_object = update.message.from_user

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT *, COUNT(user_id)
        FROM chat_stats
        WHERE chat_id = ?
        GROUP BY user_id
        ORDER BY COUNT(user_id) DESC
        LIMIT 10;
        """,
        (chat_id,),
    )

    users = cursor.fetchall()

    if not users:
        await update.message.reply_text("No messages recorded.")
        return

    text = f"Stats for <b>{update.message.chat.title}:</b>\n\n"
    total_count = sum(user[4] for user in users)

    # Ignore special case for user
    if user_object.id == 1060827049:
        text += f"<code>100% degen - {await utils.string.get_username(user_object.id, context)}</code>\n"

    for _, _, timestamp, user_id, count in users:
        percent = round(count / total_count * 100, 2)
        text += f"""<code>{percent if percent > 10 else f" {percent}"}% - {await utils.string.get_username(user_id, context)}</code>\n"""

    text += f"\nTotal messages: <b>{total_count}</b>"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )
