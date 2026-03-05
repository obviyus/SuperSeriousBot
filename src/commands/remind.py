import datetime
import html
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.db import get_db
from utils.decorators import command
from utils.messages import get_message

IST_ALIAS_PATTERN = re.compile(r"\bIST\b", re.IGNORECASE)


def tg_time(unix_time: int, fallback_text: str, format_string: str | None = None) -> str:
    format_attr = f' format="{format_string}"' if format_string else ""
    return (
        f'<tg-time unix="{unix_time}"{format_attr}>'
        f"{html.escape(fallback_text)}"
        "</tg-time>"
    )


def parse_target_time(time_text: str) -> datetime.datetime | None:
    import dateparser

    normalized_time_text = IST_ALIAS_PATTERN.sub("UTC+0530", time_text)
    parsed_time = dateparser.parse(
        normalized_time_text,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "UTC",
            "TO_TIMEZONE": "UTC",
        },
    )
    if parsed_time is None:
        return None
    if parsed_time.tzinfo is None:
        parsed_time = parsed_time.replace(tzinfo=datetime.UTC)
    return parsed_time.astimezone(datetime.UTC)


async def reminder_list(user_id: int, chat_id: int) -> str:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, title, target_time
            FROM reminders WHERE user_id = ? AND chat_id = ? AND target_time > STRFTIME('%s', 'now');
            """,
            (user_id, chat_id),
        ) as cursor:
            results = await cursor.fetchall()

    text = "⏰ Your reminders in this chat:\n"

    for index, reminder in enumerate(results):
        target_unix = int(reminder["target_time"])
        fallback_time = datetime.datetime.fromtimestamp(
            target_unix, datetime.UTC
        ).strftime("%Y-%m-%d %H:%M UTC")
        text += (
            f"\n{index + 1}. <code>{html.escape(reminder['title'])}</code> "
            f"{tg_time(target_unix, fallback_time, 'r')}"
        )

    return text


@command(
    triggers=["remind"],
    usage="/remind [REMINDER_NAME] [TARGET_TIME]",
    example="/remind Japan Trip - 5 months later",
    description="Create a reminder with a trigger time for this group.",
)
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Create a reminder with a trigger time for this group."""
    if not message.from_user:
        return

    if not context.args:
        async with get_db() as conn:
            async with conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM reminders WHERE user_id = ? AND chat_id = ? AND target_time > STRFTIME('%s', 'now');
                """,
                (message.from_user.id, message.chat_id),
            ) as cursor:
                existing_reminders = await cursor.fetchone()

        if existing_reminders and existing_reminders["count"] > 0:
            await message.reply_text(
                text=await reminder_list(message.from_user.id, message.chat_id),
                parse_mode=ParseMode.HTML,
            )
            return

        await commands.usage_string(message, remind)
        return

    full_args = " ".join(context.args)
    if " - " not in full_args:
        await commands.usage_string(message, remind)
        return

    title, target_time_text = full_args.split(" - ", maxsplit=1)
    title = title.strip()
    target_time_text = target_time_text.strip()

    target_time = parse_target_time(target_time_text)

    if target_time is None:
        await message.reply_text(
            "Invalid date/time format. Please provide a valid date and time."
        )
        return

    if target_time < datetime.datetime.now(datetime.UTC):
        await message.reply_text(
            "The specified time is in the past. Please provide a future date and time."
        )
        return

    target_unix = int(target_time.timestamp())

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO reminders (chat_id, user_id, title, target_time)
            VALUES (?, ?, ?, ?);
            """,
            (
                message.chat_id,
                message.from_user.id,
                title,
                target_unix,
            ),
        )
        await conn.commit()

    await message.reply_text(
        text=(
            f"I will remind you about <code>{html.escape(title)}</code> on "
            f"{tg_time(target_unix, target_time.strftime('%B %d, %Y at %I:%M%p %Z'), 'wDT')}"
        ),
        parse_mode=ParseMode.HTML,
    )


async def worker_reminder(context: ContextTypes.DEFAULT_TYPE):
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, title, target_time, user_id, chat_id
            FROM reminders
            WHERE target_time > STRFTIME('%s', 'now')
            AND target_time <= STRFTIME('%s', 'now', '+1 minutes');
            """
        ) as cursor:
            existing_reminders = await cursor.fetchall()

    for reminder in existing_reminders:
        text = (
            f"⏰ <code>{html.escape(reminder['title'])}</code>\n\n"
            f"@{await utils.get_username(reminder['user_id'], context)}"
        )
        await context.bot.send_message(
            reminder["chat_id"], text, parse_mode=ParseMode.HTML
        )
