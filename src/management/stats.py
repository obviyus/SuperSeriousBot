import sqlite3
from datetime import datetime

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

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

    user_object = update.message.from_user
    if user_object.username:
        username_lower = user_object.username.lower()

        # Store last seen time and message link in Redis
        redis.set(f"seen:{username_lower}", round(datetime.now().timestamp()))

        if update.message.link:
            redis.set(f"seen_message:{username_lower}", update.message.link)

        # Store the original casing of the username
        redis.set(f"username_case:{username_lower}", user_object.username)

        # Map user ID to the correctly cased username
        redis.set(f"user_id:{user_object.id}", user_object.username)

        # Map the lowercase username to the user ID
        redis.set(f"username:{username_lower}", user_object.id)

    cursor = sqlite_conn.cursor()
    chat_id = update.message.chat_id
    try:
        cursor.execute(
            "INSERT INTO chat_stats (chat_id, user_id, message_id) VALUES (?, ?, ?)",
            (chat_id, user_object.id, update.message.message_id),
        )

        if update.message.text:
            cursor.execute(
                """
                SELECT fts FROM group_settings
                WHERE chat_id = ?;
                """,
                (update.message.chat_id,),
            )
            result = cursor.fetchone()

            is_enabled = result["fts"] if result else False
            if is_enabled:
                cursor.execute(
                    "UPDATE chat_stats SET message_text = ? WHERE rowid = ?",
                    (update.message.text, cursor.lastrowid),
                )
    except sqlite3.IntegrityError:
        pass


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

    username_input = context.args[0].split("@")
    if len(username_input) <= 1:
        await commands.usage_string(update.message, get_last_seen)
        return

    username_lower = username_input[1].lower()

    last_seen = redis.get(f"seen:{username_lower}")
    message_link = redis.get(f"seen_message:{username_lower}")

    username_display = redis.get(f"username_case:{username_lower}")
    if not username_display:
        username_display = f"@{username_input[1]}"

    if not last_seen:
        not_seen_text = f"{username_display} has never been seen."
        await update.message.reply_text(not_seen_text)
        return

    try:
        last_seen = int(last_seen)
    except ValueError:
        last_seen = datetime.fromisoformat(last_seen).timestamp()

    # Create a link to the message if available
    html_message = f"\n\n🔗 <a href='{message_link}'>Link</a>" if message_link else ""

    user_mention_string = mention_html(username_display, username_display)
    await update.message.reply_text(
        f"Last message from {user_mention_string} was {await readable_time(last_seen)} ago.{html_message}",
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
