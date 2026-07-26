from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils.decorators import command
from utils.messages import get_message


async def _fetch_scalar(query: str) -> int:
    async with get_db() as conn, conn.execute(query) as cursor:
        result = await cursor.fetchone()
    return result[0] if result and result[0] else 0


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
    triggers=["botstats"],
    usage="/botstats",
    example="/botstats",
    description="Get usage stats of all bot commands.",
)
async def get_command_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT *, COUNT(id) AS command_count
            FROM command_stats
            GROUP BY command
            ORDER BY COUNT(id) DESC
            LIMIT 10;
            """
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    total_count = await _fetch_scalar(
        "SELECT COUNT(*) FROM command_stats;",
    )
    await _reply_ranked_stats(
        message,
        context,
        "Stats",
        [f"<code>{row['command_count']:4} - /{row['command']}</code>" for row in rows],
        total_count,
    )
