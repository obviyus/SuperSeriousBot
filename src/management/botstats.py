from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils import readable_time
from utils.decorators import command
from utils.messages import get_message


async def _fetch_scalar(query: str, key: int | str = 0) -> int:
    async with get_db() as conn:
        async with conn.execute(query) as cursor:
            result = await cursor.fetchone()
    return result[key] if result and result[key] else 0


async def _reply_ranked_stats(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    title: str,
    lines: list[str],
    total: int,
) -> None:
    text = f"{title} for <b>@{context.bot.username}:</b>\n\n"
    if lines:
        text += "\n".join(lines)
    text += f"\n\nTotal: <b>{total}</b>"
    await message.reply_text(text, parse_mode=ParseMode.HTML)


@command(
    triggers=["users"],
    usage="/users",
    example="/users",
    description="Get number of users that use this bot.",
)
async def get_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    user_count = await _fetch_scalar("SELECT COUNT(DISTINCT user_id) FROM chat_stats;")
    await message.reply_text(
        f"@{context.bot.username} is used by <b>{user_count}</b> users.",
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["groups"],
    usage="/groups",
    example="/groups",
    description="Get number of groups that use bot.",
)
async def get_total_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    chat_count = await _fetch_scalar("SELECT COUNT(DISTINCT chat_id) FROM chat_stats;")
    await message.reply_text(
        f"@{context.bot.username} is used in <b>{chat_count}</b> groups.",
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["uptime"],
    usage="/uptime",
    example="/uptime",
    description="Get duration since the bot instance was started.",
)
async def get_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return

    from main import bot_startup_time

    if not bot_startup_time:
        await message.reply_text("This bot has not been started yet.")
        return

    await message.reply_text(
        f"@{context.bot.username} has been online for <b>{await readable_time(int(bot_startup_time))}</b>.",
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["botstats"],
    usage="/botstats",
    example="/botstats",
    description="Get usage stats of all bot commands.",
)
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
    total_count = await _fetch_scalar(
        "SELECT id FROM main.command_stats ORDER BY id DESC LIMIT 1;",
        "id",
    )
    await _reply_ranked_stats(
        message,
        context,
        "Stats",
        [f"<code>{row['command_count']:4} - /{row['command']}</code>" for row in rows],
        total_count,
    )


@command(
    triggers=["objects"],
    usage="/objects",
    example="/objects",
    description="Get the top 10 most fetched objects from the object store.",
)
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
    total_fetch_count = await _fetch_scalar(
        "SELECT SUM(fetch_count) AS fetch_count FROM main.object_store;",
        "fetch_count",
    )
    await _reply_ranked_stats(
        message,
        context,
        "Object Stats",
        [f"<code>{row['key']:4} - {row['fetch_count']}</code>" for row in rows],
        total_fetch_count,
    )
