import datetime
import html
import re
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import ChatMigrated, TelegramError
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from config.logger import logger
from utils.decorators import command
from utils.messages import get_message

IST_ALIAS_PATTERN = re.compile(r"\bIST\b", re.IGNORECASE)
IST_TIMEZONE = ZoneInfo("Asia/Kolkata")
REMINDER_BATCH_LIMIT = 50
REMINDER_CLAIM_LEASE_SECONDS = 5 * 60


def tg_time(
    unix_time: int, fallback_text: str, format_string: str | None = None
) -> str:
    format_attr = f' format="{format_string}"' if format_string else ""
    return (
        f'<tg-time unix="{unix_time}"{format_attr}>'
        f"{html.escape(fallback_text)}"
        "</tg-time>"
    )


def parse_reminder_time(
    text: str,
    *,
    now: datetime.datetime | None = None,
) -> datetime.datetime | None:
    import dateparser

    current_time = now or datetime.datetime.now(datetime.UTC)
    has_ist = bool(IST_ALIAS_PATTERN.search(text))
    timezone = IST_TIMEZONE if has_ist else datetime.UTC
    normalized_text = IST_ALIAS_PATTERN.sub("", text).strip()
    target_time = dateparser.parse(
        normalized_text,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "Asia/Kolkata" if has_ist else "UTC",
            "TO_TIMEZONE": "UTC",
            "RELATIVE_BASE": current_time.astimezone(timezone),
            "PREFER_DATES_FROM": "future",
        },
    )
    if target_time is None:
        return None
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone)
    return target_time.astimezone(datetime.UTC)


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
    if not message.from_user:
        return

    if not context.args:
        async with (
            get_db() as conn,
            conn.execute(
                """
                SELECT title, target_time
                FROM reminders
                WHERE user_id = ? AND chat_id = ?
                ORDER BY target_time ASC;
                """,
                (message.from_user.id, message.chat_id),
            ) as cursor,
        ):
            reminders = await cursor.fetchall()

        if reminders:
            text = "⏰ Your reminders in this chat:\n"
            for index, reminder in enumerate(reminders, start=1):
                target_unix = int(reminder["target_time"])
                fallback_time = datetime.datetime.fromtimestamp(
                    target_unix,
                    datetime.UTC,
                ).strftime("%Y-%m-%d %H:%M UTC")
                text += (
                    f"\n{index}. <code>{html.escape(reminder['title'])}</code> "
                    f"{tg_time(target_unix, fallback_time, 'r')}"
                )
            await message.reply_text(text=text, parse_mode=ParseMode.HTML)
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

    now = datetime.datetime.now(datetime.UTC)
    target_time = parse_reminder_time(target_time_text, now=now)

    if target_time is None:
        await message.reply_text(
            "Invalid date/time format. Please provide a valid date and time."
        )
        return

    if target_time < now:
        await message.reply_text(
            "The specified time is in the past. Please provide a future date and time."
        )
        return

    target_unix = int(target_time.timestamp())

    async with get_db() as conn:
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

    await message.reply_text(
        text=(
            f"I will remind you about <code>{html.escape(title)}</code> on "
            f"{tg_time(target_unix, target_time.strftime('%B %d, %Y at %I:%M%p %Z'), 'wDT')}"
        ),
        parse_mode=ParseMode.HTML,
    )


async def worker_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = int(datetime.datetime.now(datetime.UTC).timestamp())
    expired_claim_time = now - REMINDER_CLAIM_LEASE_SECONDS

    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT id, title, target_time, user_id, chat_id
            FROM reminders
            WHERE target_time <= ?
            AND (claim_time IS NULL OR claim_time <= ?)
            ORDER BY target_time ASC
            LIMIT ?;
            """,
            (now, expired_claim_time, REMINDER_BATCH_LIMIT),
        ) as cursor,
    ):
        existing_reminders = await cursor.fetchall()

    for reminder in existing_reminders:
        async with get_db() as conn:
            claim = await conn.execute(
                """
                UPDATE reminders
                SET claim_time = ?, attempt_count = attempt_count + 1, last_error = NULL
                WHERE id = ?
                AND (claim_time IS NULL OR claim_time <= ?)
                """,
                (now, reminder["id"], expired_claim_time),
            )
            if claim.rowcount == 0:
                continue

        text = (
            f'⏰ <a href="tg://user?id={reminder["user_id"]}">Reminder for you</a>'
            f"\n\n<code>{html.escape(reminder['title'])}</code>"
        )
        try:
            await deliver_reminder(context, reminder, text)
        except TelegramError as exc:
            async with get_db() as conn:
                await conn.execute(
                    "UPDATE reminders SET last_error = ? WHERE id = ?",
                    (str(exc), reminder["id"]),
                )
            logger.error("Reminder delivery failed id=%s error=%s", reminder["id"], exc)
        else:
            async with get_db() as conn:
                await conn.execute(
                    "DELETE FROM reminders WHERE id = ?", (reminder["id"],)
                )


async def deliver_reminder(
    context: ContextTypes.DEFAULT_TYPE,
    reminder,
    text: str,
) -> None:
    try:
        await context.bot.send_message(
            reminder["chat_id"], text, parse_mode=ParseMode.HTML
        )
    except ChatMigrated as exc:
        async with get_db() as conn:
            await conn.execute(
                "UPDATE reminders SET chat_id = ? WHERE chat_id = ?",
                (exc.new_chat_id, reminder["chat_id"]),
            )
        await context.bot.send_message(exc.new_chat_id, text, parse_mode=ParseMode.HTML)
