import heapq

from telegram import MessageEntity, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import management
from db import redis, sqlite_conn
from utils import readable_time


async def get_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get number of users of this bot.
    """

    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_stats;")

    await update.message.reply_text(
        f"@{context.bot.username} is used by <b>{cursor.fetchone()[0]}</b> users.",
        parse_mode=ParseMode.HTML,
    )


async def get_total_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get number of chats this bot is used in.
    """

    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_stats;")

    await update.message.reply_text(
        f"@{context.bot.username} is used in <b>{cursor.fetchone()[0]}</b> groups.",
        parse_mode=ParseMode.HTML,
    )


async def get_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get uptime of this bot.
    """

    uptime = redis.get("bot_startup_time")
    if not uptime:
        await update.message.reply_text("This bot has not been started yet.")
        return

    uptime = int(float(uptime))
    await update.message.reply_text(
        f"@{context.bot.username} has been online for <b>{await readable_time(uptime)}</b>.",
        parse_mode=ParseMode.HTML,
    )


async def increment_command_count(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Increment command count for a /<command> invocation.
    """
    if not update.message:
        return

    await management.increment(update, context)
    command = next(
        iter(update.message.parse_entities([MessageEntity.BOT_COMMAND]).values()), None
    )

    if not command:
        return

    command = command[1:]
    redis.incr(f"command:{command}", 1)


async def get_command_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get usage stats for all commands.
    """

    commands = []
    for command in redis.scan_iter("command:*"):
        heapq.heappush(
            commands,
            (-1 * int(redis.get(command)), command.replace("command:", "")),
        )

    text, total = f"<u>Stats for @{context.bot.username}</u>:\n\n", 0
    for count, command in heapq.nlargest(10, commands):
        count *= -1
        text += f"<pre>/{command}: {count}</pre>\n"
        total += count

    text += f"\n<pre>Total: {total}</pre>"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )
