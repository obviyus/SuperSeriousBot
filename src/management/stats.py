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
    for _, user_id, count in rows:
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
    # Prefer explicit @username arg
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

    # If replying to a user
    if message and message.reply_to_message and message.reply_to_message.from_user:
        replied = message.reply_to_message.from_user
        return replied.id, replied.username or replied.full_name

    # Fallback to the caller
    if message and message.from_user:
        caller = message.from_user
        return caller.id, caller.username or caller.full_name

    return None, None


@usage("/stats")
@example("/stats")
@triggers(["stats"])
@description("Get message count by user for the last day.")
async def get_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    chat_id = message.chat_id

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT create_time,user_id, COUNT(user_id) AS user_count
                FROM chat_stats
            WHERE chat_id = ? AND
                create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime')
            GROUP BY user_id
            ORDER BY COUNT(user_id) DESC
            LIMIT 10;
            """,
            (chat_id,),
        ) as cursor:
            users = list(await cursor.fetchall())

        async with conn.execute(
            """
            SELECT COUNT(id) AS total_count
                FROM chat_stats
            WHERE chat_id = ? AND
                create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime');
            """,
            (chat_id,),
        ) as cursor:
            result = await cursor.fetchone()
            total_count = result["total_count"] if result else 0

    await stat_string_builder(users, message, context, total_count)


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
    chat_id = message.chat_id

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT create_time, user_id, COUNT(user_id) AS user_count
                FROM chat_stats
            WHERE chat_id = ?
            GROUP BY user_id
            ORDER BY COUNT(user_id) DESC
            LIMIT 10;
            """,
            (chat_id,),
        ) as cursor:
            users = list(await cursor.fetchall())

        async with conn.execute(
            """
            SELECT COUNT(id) AS total_count
                FROM chat_stats
            WHERE chat_id = ?;
            """,
            (chat_id,),
        ) as cursor:
            result = await cursor.fetchone()
            total_count = result["total_count"] if result else 0

    await stat_string_builder(users, message, context, total_count)


@usage("/ustats [username]")
@example("/ustats @obviyus")
@triggers(["ustats", "ustat", "userstats"])
@description("Show a user's weekly activity and other stats in this group.")
async def get_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
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

    # Fetch per-day counts for the user, last 7 days
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT DATE(create_time, 'localtime') AS d, COUNT(*) AS cnt
            FROM chat_stats
            WHERE chat_id = ?
              AND user_id = ?
              AND create_time >= DATE('now', '-6 days', 'localtime')
              AND create_time < DATE('now', '+1 day', 'localtime')
            GROUP BY d
            """,
            (chat_id, user_id),
        ) as cursor:
            rows = list(await cursor.fetchall())

        counts_map = {row["d"]: row["cnt"] for row in rows}
        week_counts = [int(counts_map.get(k, 0)) for k in day_keys]
        user_week_total = sum(week_counts)

        # Group total for the same period
        async with conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM chat_stats
            WHERE chat_id = ?
              AND create_time >= DATE('now', '-6 days', 'localtime')
              AND create_time < DATE('now', '+1 day', 'localtime')
            """,
            (chat_id,),
        ) as cursor:
            result = await cursor.fetchone()
            group_week_total = int(result["total"]) if result and result["total"] else 0

        # Most active hour (last 30 days)
        async with conn.execute(
            """
            SELECT strftime('%H', create_time, 'localtime') AS hour, COUNT(*) AS cnt
            FROM chat_stats
            WHERE chat_id = ? AND user_id = ?
              AND create_time >= DATE('now', '-30 days', 'localtime')
            GROUP BY hour
            ORDER BY cnt DESC
            LIMIT 1;
            """,
            (chat_id, user_id),
        ) as cursor:
            hour_row = await cursor.fetchone()
            top_hour = hour_row["hour"] if hour_row else None

        # Most active day of week (0=Sun..6=Sat) across recent history (90d)
        async with conn.execute(
            """
            SELECT strftime('%w', create_time, 'localtime') AS dow, COUNT(*) AS cnt
            FROM chat_stats
            WHERE chat_id = ? AND user_id = ?
              AND create_time >= DATE('now', '-90 days', 'localtime')
            GROUP BY dow
            ORDER BY cnt DESC
            LIMIT 1;
            """,
            (chat_id, user_id),
        ) as cursor:
            dow_row = await cursor.fetchone()
            top_dow = dow_row["dow"] if dow_row else None

        # Dates with at least one message (for streak calc, last 60 days)
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
            date_rows = list(await cursor.fetchall())
            active_dates = {r["d"] for r in date_rows}

        # Lifetime total for this chat
        async with conn.execute(
            "SELECT COUNT(*) AS total FROM chat_stats WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ) as cursor:
            result = await cursor.fetchone()
            lifetime_total = int(result["total"]) if result and result["total"] else 0

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
    dow_names = {
        "0": "Sun",
        "1": "Mon",
        "2": "Tue",
        "3": "Wed",
        "4": "Thu",
        "5": "Fri",
        "6": "Sat",
    }
    top_dow_name = dow_names.get(top_dow, "-") if top_dow is not None else "-"
    if top_hour is not None:
        hour_int = int(top_hour)
        top_hour_label = f"{hour_int:02d}:00-{(hour_int + 1) % 24:02d}:00"
    else:
        top_hour_label = "-"

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
