from datetime import datetime

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils.string
from config.db import redis, sqlite_conn
from utils import readable_time
from utils.decorators import description, example, triggers, usage


async def increment(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Increment message count for a user. Also store last seen time in Redis.
    """
    if not update.message:
        return

    chat_id = update.message.chat.id
    user_object = update.message.from_user

    # Set last seen time and message link in Redis
    redis.set(
        f"seen:{user_object.username}",
        round(datetime.now().timestamp()),
    )

    if update.message.link:
        redis.set(f"seen_message:{user_object.username}", update.message.link)

    # Update user_id vs. username in Redis
    redis.set(
        f"user_id:{user_object.id}", user_object.username or user_object.first_name
    )
    # Update username vs. user_id in Redis
    redis.set(
        f"username:{user_object.username.lower() if user_object.username else user_object.first_name}",
        user_object.id,
    )

    cursor = sqlite_conn.cursor()
    cursor.execute(
        "INSERT INTO chat_stats (chat_id, user_id) VALUES (?, ?)",
        (chat_id, user_object.id),
    )


async def stat_string_builder(
    rows: list,
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    total_count: int,
) -> None:
    if not rows:
        await message.reply_text("No messages recorded.")
        return

    text = f"Stats for <b>{message.chat.title}:</b>\n\n"
    for _, _, timestamp, user_id, count in rows:
        percent = round(count / total_count * 100, 2)
        text += f"""<code>{percent:4.1f}% - {await utils.string.get_first_name(user_id, context)}</code>\n"""

    text += f"\nTotal messages: <b>{total_count}</b>"
    await message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


@triggers(["seen"])
@usage("/seen [username]")
@example("/seen @obviyus")
@description("Get duration since last message of a user.")
async def get_last_seen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await commands.usage_string(update.message, get_last_seen)
        return

    username = context.args[0].split("@")
    if len(username) <= 1:
        await commands.usage_string(update.message, get_last_seen)
        return

    username = username[1]

    # Get last seen time in Redis
    last_seen = redis.get(f"seen:{username}")
    if not last_seen:
        await update.message.reply_text(f"@{username} has never been seen.")
        return

    message_link = redis.get(f"seen_message:{username}")
    html_message = f"\n\n🔗 <a href='{message_link}'>Link</a>" if message_link else ""

    try:
        last_seen = int(last_seen)
    except ValueError:
        last_seen = datetime.fromisoformat(last_seen).timestamp()

    await update.message.reply_text(
        f"<a href='https://t.me/{username}'>@{username}</a>'s last message was {await readable_time(last_seen)} ago."
        f"{html_message}",
        disable_web_page_preview=True,
        disable_notification=True,
        parse_mode=ParseMode.HTML,
    )


@usage("/stats")
@example("/stats")
@triggers(["stats"])
@description("Get message count by user for the last day.")
async def get_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """SELECT *, COUNT(user_id) AS user_count
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
    cursor.execute(
        """SELECT COUNT(id) AS total_count
        FROM chat_stats 
        WHERE chat_id = ? AND 
        create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime');
        """,
        (chat_id,),
    )

    await stat_string_builder(
        users, update.message, context, cursor.fetchone()["total_count"]
    )


@usage("/gstats")
@example("/gstats")
@triggers(["gstats"])
@description("Get total message count by user of this group.")
async def get_total_chat_stats(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = update.message.chat_id

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT *, COUNT(user_id) AS user_count
        FROM chat_stats
        WHERE chat_id = ?
        GROUP BY user_id
        ORDER BY COUNT(user_id) DESC
        LIMIT 10;
        """,
        (chat_id,),
    )

    users = cursor.fetchall()
    cursor.execute(
        """
        SELECT COUNT(id) AS total_count
        FROM chat_stats
        WHERE chat_id = ?;
        """,
        (chat_id,),
    )

    await stat_string_builder(
        users, update.message, context, cursor.fetchone()["total_count"]
    )
