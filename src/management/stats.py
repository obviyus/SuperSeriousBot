import asyncio
from datetime import datetime, timedelta

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

import commands
import utils.string
from config.db import get_db
from utils import readable_time
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message

_DOW_NAMES = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


async def stat_string_builder(
    rows: list,
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    total_count: int,
) -> None:
    if not rows:
        await message.reply_text("No messages recorded.")
        return

    # Parallel fetch all names (cache hits are instant, misses run concurrently)
    user_ids = [user_id for _, user_id, _ in rows]
    names = await asyncio.gather(
        *(utils.string.get_first_name(uid, context) for uid in user_ids)
    )

    # Build output with list join (avoids O(n²) string concat)
    lines = [f"Stats for <b>{message.chat.title}:</b>", ""]
    for (_, _user_id, count), name in zip(rows, names, strict=True):
        percent = count / total_count * 100
        lines.append(f"<code>{percent:4.1f}% - {name}</code>")
    lines.append(f"\nTotal messages: <b>{total_count}</b>")

    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@triggers(["seen"])
@usage("/seen [username]")
@example("/seen @obviyus")
@description("Get duration since last message of a user.")
async def get_last_seen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not context.args:
        await commands.usage_string(message, get_last_seen)
        return

    username_input = context.args[0].split("@")
    if len(username_input) <= 1:
        await commands.usage_string(message, get_last_seen)
        return

    username_lower = username_input[1].lower()

    async with get_db() as conn:
        async with conn.execute(
            "SELECT username, last_seen, last_message_link FROM user_stats WHERE LOWER(username) = ?",
            (username_lower,),
        ) as cursor:
            user_stats = await cursor.fetchone()

    if not user_stats:
        await message.reply_text(f"@{username_input[1]} has never been seen.")
        return

    last_seen = user_stats["last_seen"]
    message_link = user_stats["last_message_link"]
    username_display = user_stats["username"]

    try:
        last_seen_int = int(last_seen)
    except ValueError:
        last_seen_int = int(datetime.fromisoformat(last_seen).timestamp())

    # Create a link to the message if available
    html_message = f"\n\n🔗 <a href='{message_link}'>Link</a>" if message_link else ""

    user_mention_string = mention_html(username_display, username_display)
    await message.reply_text(
        f"Last message from {user_mention_string} was {await readable_time(last_seen_int)} ago.{html_message}",
        disable_web_page_preview=True,
        disable_notification=True,
        parse_mode=ParseMode.HTML,
    )


def _sparkline(values: list[int]) -> str:
    """Return a unicode sparkline for a list of non-negative integers."""
    if not values:
        return ""
    levels = "▁▂▃▄▅▆▇█"
    max_value = max(values) or 1
    return "".join(
        levels[min(len(levels) - 1, int(v / max_value * (len(levels) - 1)))]
        for v in values
    )


def _format_horizontal_bars(
    labels: list[str], values: list[int], width: int = 20
) -> str:
    """Return a simple monospaced horizontal bar chart string."""
    if not values:
        return ""
    max_value = max(values) or 1
    lines: list[str] = []
    for label, value in zip(labels, values, strict=False):
        bar_len = 0 if max_value == 0 else round(value / max_value * width)
        bar = "█" * bar_len
        lines.append(f"{label:>3} | {bar:<{width}} {value}")
    return "\n".join(lines)


async def _resolve_target_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> tuple[int | None, str | None]:
    """Resolve target user_id and display username from args/reply/self."""
    message = get_message(update)

    # Priority 1: explicit @username arg → DB lookup
    if context.args:
        username_input = context.args[0].split("@")
        if len(username_input) > 1:
            username_lower = username_input[1].lower()
            async with get_db() as conn:
                async with conn.execute(
                    "SELECT user_id, username FROM user_stats WHERE LOWER(username) = ?",
                    (username_lower,),
                ) as cursor:
                    row = await cursor.fetchone()
            if row:
                return int(row["user_id"]), row["username"]

    # Priority 2: reply target, else caller (unified extraction)
    user = (
        message.reply_to_message.from_user
        if message and message.reply_to_message
        else None
    ) or (message.from_user if message else None)
    if user:
        return user.id, user.username or user.full_name

    return None, None


async def _fetch_chat_stats(chat_id: int, today_only: bool = False) -> tuple[list, int]:
    """Fetch top users and total count, optionally filtered to today."""
    time_clause = (
        "AND create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime')"
        if today_only
        else ""
    )

    async with get_db() as conn:
        async with conn.execute(
            f"""
            SELECT create_time, user_id, COUNT(user_id) AS user_count
            FROM chat_stats
            WHERE chat_id = ? {time_clause}
            GROUP BY user_id
            ORDER BY COUNT(user_id) DESC
            LIMIT 10;
            """,
            (chat_id,),
        ) as cursor:
            users = list(await cursor.fetchall())

        async with conn.execute(
            f"""
            SELECT COUNT(id) AS total_count
            FROM chat_stats
            WHERE chat_id = ? {time_clause};
            """,
            (chat_id,),
        ) as cursor:
            result = await cursor.fetchone()
            total_count: int = result["total_count"] if result else 0

    return users, total_count


@usage("/stats")
@example("/stats")
@triggers(["stats"])
@description("Get message count by user for the last day.")
async def get_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    users, total = await _fetch_chat_stats(message.chat_id, today_only=True)
    await stat_string_builder(users, message, context, total)


@usage("/gstats")
@example("/gstats")
@triggers(["gstats"])
@description("Get total message count by user of this group.")
async def get_total_chat_stats(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = get_message(update)
    if not message:
        return
    users, total = await _fetch_chat_stats(message.chat_id, today_only=False)
    await stat_string_builder(users, message, context, total)


@usage("/ustats [username]")
@example("/ustats @obviyus")
@triggers(["ustats", "ustat", "userstats"])
@description("Show a user's weekly activity and other stats in this group.")
async def get_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    chat_id = message.chat_id

    user_id, username_display = await _resolve_target_user(update, context)
    if not user_id:
        await message.reply_text(
            "Couldn't resolve target user. Usage: /ustats [@username]"
        )
        return

    # Build the last 7 days (oldest -> newest) date keys in localtime
    today_local = datetime.now()
    day_keys: list[str] = []
    day_labels: list[str] = []
    for i in range(6, -1, -1):
        day = today_local - timedelta(days=i)
        day_keys.append(day.strftime("%Y-%m-%d"))
        day_labels.append(day.strftime("%a"))

    # AIDEV-NOTE: Single CTE query replaces 6 sequential DB round-trips
    async with get_db() as conn:
        async with conn.execute(
            """
            WITH user_daily AS (
                SELECT DATE(create_time, 'localtime') AS d, COUNT(*) AS cnt
                FROM chat_stats
                WHERE chat_id = ? AND user_id = ?
                  AND create_time >= DATE('now', '-6 days', 'localtime')
                  AND create_time < DATE('now', '+1 day', 'localtime')
                GROUP BY d
            ),
            group_week AS (
                SELECT COUNT(*) AS total
                FROM chat_stats
                WHERE chat_id = ?
                  AND create_time >= DATE('now', '-6 days', 'localtime')
                  AND create_time < DATE('now', '+1 day', 'localtime')
            ),
            top_hour AS (
                SELECT strftime('%H', create_time, 'localtime') AS hour
                FROM chat_stats
                WHERE chat_id = ? AND user_id = ?
                  AND create_time >= DATE('now', '-30 days', 'localtime')
                GROUP BY hour
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ),
            top_dow AS (
                SELECT strftime('%w', create_time, 'localtime') AS dow
                FROM chat_stats
                WHERE chat_id = ? AND user_id = ?
                  AND create_time >= DATE('now', '-90 days', 'localtime')
                GROUP BY dow
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ),
            lifetime AS (
                SELECT COUNT(*) AS total
                FROM chat_stats
                WHERE chat_id = ? AND user_id = ?
            )
            SELECT
                'daily' AS qtype, d AS val, cnt AS cnt FROM user_daily
            UNION ALL
            SELECT 'group_total', NULL, total FROM group_week
            UNION ALL
            SELECT 'top_hour', hour, NULL FROM top_hour
            UNION ALL
            SELECT 'top_dow', dow, NULL FROM top_dow
            UNION ALL
            SELECT 'lifetime', NULL, total FROM lifetime
            """,
            (
                chat_id,
                user_id,
                chat_id,
                chat_id,
                user_id,
                chat_id,
                user_id,
                chat_id,
                user_id,
            ),
        ) as cursor:
            rows = await cursor.fetchall()

        # Parse unified result set
        counts_map: dict[str, int] = {}
        group_week_total = 0
        top_hour = None
        top_dow = None
        lifetime_total = 0

        for row in rows:
            qtype = row["qtype"]
            if qtype == "daily":
                counts_map[row["val"]] = row["cnt"]
            elif qtype == "group_total":
                group_week_total = row["cnt"] or 0
            elif qtype == "top_hour":
                top_hour = row["val"]
            elif qtype == "top_dow":
                top_dow = row["val"]
            elif qtype == "lifetime":
                lifetime_total = row["cnt"] or 0

        week_counts = [counts_map.get(k, 0) for k in day_keys]
        user_week_total = sum(week_counts)

        # Streak calculation needs active dates (separate query - still faster than 6)
        async with conn.execute(
            """
            SELECT DATE(create_time, 'localtime') AS d
            FROM chat_stats
            WHERE chat_id = ? AND user_id = ?
              AND create_time >= DATE('now', '-60 days', 'localtime')
            GROUP BY d
            """,
            (chat_id, user_id),
        ) as cursor:
            date_rows = await cursor.fetchall()
            active_dates = {r["d"] for r in date_rows}

    # Streak calculation from today backwards
    streak = 0
    probe = today_local
    while streak < 60:  # cap
        key = probe.strftime("%Y-%m-%d")
        if key in active_dates:
            streak += 1
            probe -= timedelta(days=1)
        else:
            break

    # Build charts
    spark = _sparkline(week_counts)
    bars = _format_horizontal_bars(day_labels, week_counts)

    # Friendly labels
    top_dow_name = _DOW_NAMES[int(top_dow)] if top_dow is not None else "-"
    top_hour_label = (
        f"{int(top_hour):02d}:00-{(int(top_hour) + 1) % 24:02d}:00"
        if top_hour is not None
        else "-"
    )

    share = (
        (user_week_total / group_week_total * 100.0) if group_week_total > 0 else 0.0
    )
    avg_per_day = user_week_total / 7.0

    # Header name
    target_name = username_display or str(user_id)
    header = f"User stats for <b>{target_name}</b> in <b>{message.chat.title}</b>\n"

    if user_week_total == 0:
        await message.reply_text(
            header + "\nNo messages in the last 7 days.",
            parse_mode=ParseMode.HTML,
        )
        return

    text = (
        header
        + f"\nLast 7d: <b>{user_week_total}</b> msgs ({share:.1f}% of group) • avg {avg_per_day:.2f}/day"
        + f"\nLifetime in this chat: <b>{lifetime_total}</b> msgs"
        + (
            f"\nMost active hour: <b>{top_hour_label}</b> \nMost active day: <b>{top_dow_name}</b>"
        )
        + (f"\nCurrent streak: <b>{streak}</b> day(s)" if streak > 0 else "")
        + "\n\n<pre>"
        + bars
        + "</pre>"
        + (f"\nSparkline: <code>{spark}</code>" if spark else "")
    )

    await message.reply_text(text, parse_mode=ParseMode.HTML)
