from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils import readable_time
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


@usage("/users")
@example("/users")
@triggers(["users"])
@description("Get number of users that use this bot.")
async def get_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    async with get_db() as conn:
        async with conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM chat_stats;"
        ) as cursor:
            result = await cursor.fetchone()
            user_count = result[0] if result else 0

    await message.reply_text(
        f"@{context.bot.username} is used by <b>{user_count}</b> users.",
        parse_mode=ParseMode.HTML,
    )


@usage("/groups")
@example("/groups")
@triggers(["groups"])
@description("Get number of groups that use bot.")
async def get_total_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    async with get_db() as conn:
        async with conn.execute(
            "SELECT COUNT(DISTINCT chat_id) FROM chat_stats;"
        ) as cursor:
            result = await cursor.fetchone()
            chat_count = result[0] if result else 0

    await message.reply_text(
        f"@{context.bot.username} is used in <b>{chat_count}</b> groups.",
        parse_mode=ParseMode.HTML,
    )


@usage("/uptime")
@example("/uptime")
@triggers(["uptime"])
@description("Get duration since the bot instance was started.")
async def get_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return

    # Late import to avoid circular dependency
    from main import bot_startup_time

    if not bot_startup_time:
        await message.reply_text("This bot has not been started yet.")
        return

    await message.reply_text(
        f"@{context.bot.username} has been online for <b>{await readable_time(int(bot_startup_time))}</b>.",
        parse_mode=ParseMode.HTML,
    )


@usage("/botstats")
@example("/botstats")
@triggers(["botstats"])
@description("Get usage stats of all bot commands.")
async def get_command_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT *, COUNT(id) AS command_count
            FROM command_stats
            GROUP BY command
            ORDER BY COUNT(id) DESC
            LIMIT 10;
            """
        ) as cursor:
            rows = await cursor.fetchall()

        async with conn.execute(
            """
            SELECT id FROM main.command_stats ORDER BY id DESC LIMIT 1;
            """
        ) as cursor:
            result = await cursor.fetchone()
            total_count = result["id"] if result else 0

    text = f"Stats for <b>@{context.bot.username}:</b>\n\n"
    for row in rows:
        text += f"""<code>{row["command_count"]:4} - /{row["command"]}</code>\n"""

    text += f"\nTotal: <b>{total_count}</b>"
    await message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


@usage("/objects")
@example("/objects")
@triggers(["objects"])
@description("Get the top 10 most fetched objects from the object store.")
async def get_object_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT key, fetch_count
            FROM object_store
            ORDER BY fetch_count DESC
            LIMIT 10;
            """
        ) as cursor:
            rows = await cursor.fetchall()

        async with conn.execute(
            """
            SELECT SUM(fetch_count) AS fetch_count FROM main.object_store;
            """
        ) as cursor:
            result = await cursor.fetchone()
            total_fetch_count = (
                result["fetch_count"] if result and result["fetch_count"] else 0
            )

    text = f"Object Stats for <b>@{context.bot.username}:</b>\n\n"
    for row in rows:
        text += f"""<code>{row["key"]:4} - {row["fetch_count"]}</code>\n"""

    text += f"\nTotal: <b>{total_fetch_count}</b>"
    await message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )
