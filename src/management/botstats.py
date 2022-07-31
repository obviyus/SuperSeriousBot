import heapq

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import redis, sqlite_conn
from utils import readable_time
from utils.decorators import description, example, triggers, usage


@triggers(["users"])
@description("Get number of users that user this bot.")
@usage("/users")
@example("/users")
async def get_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_stats;")

    await update.message.reply_text(
        f"@{context.bot.username} is used by <b>{cursor.fetchone()[0]}</b> users.",
        parse_mode=ParseMode.HTML,
    )


@triggers(["groups"])
@description("Get number of groups that use bot.")
@usage("/groups")
@example("/groups")
async def get_total_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_stats;")

    await update.message.reply_text(
        f"@{context.bot.username} is used in <b>{cursor.fetchone()[0]}</b> groups.",
        parse_mode=ParseMode.HTML,
    )


@triggers(["uptime"])
@description("Get duration since the bot instance was started.")
@usage("/uptime")
@example("/uptime")
async def get_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime = redis.get("bot_startup_time")
    if not uptime:
        await update.message.reply_text("This bot has not been started yet.")
        return

    uptime = int(float(uptime))
    await update.message.reply_text(
        f"@{context.bot.username} has been online for <b>{await readable_time(uptime)}</b>.",
        parse_mode=ParseMode.HTML,
    )


@triggers(["botstats"])
@description("Get usage stats of all bot commands.")
@usage("/botstats")
@example("/botstats")
async def get_command_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands = []
    for command in redis.scan_iter("command:*"):
        heapq.heappush(
            commands,
            (-1 * int(redis.get(command)), command.replace("command:", "")),
        )

    text, total = f"<u>Stats for @{context.bot.username}</u>:\n\n", 0
    for count, command in heapq.nlargest(10, commands):
        count *= -1
        text += f"<pre>/{command:9}: {count}</pre>\n"
        total += count

    text += f"\n<b>Total: {total}</b>"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )
