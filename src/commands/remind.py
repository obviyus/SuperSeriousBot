import datetime

import dateparser
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.db import get_db
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


def readable_time(time: datetime.datetime) -> str:
    now = datetime.datetime.now()
    time_difference = time - now

    days = time_difference.days
    hours, remainder = divmod(time_difference.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    time_left = ""
    if days > 0:
        time_left += f"{days} days, "
    if hours > 0:
        time_left += f"{hours} hours, "
    if minutes > 0:
        time_left += f"{minutes} minutes"

    return time_left.rstrip(", ")


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
        parsed_time = datetime.datetime.fromtimestamp(reminder["target_time"])
        text += f"\n{index + 1}. <code>{reminder['title']}</code> in {readable_time(parsed_time)}"

    return text


@triggers(["remind"])
@usage("/remind [REMINDER_NAME] [TARGET_TIME]")
@description("Create a reminder with a trigger time for this group.")
@example("/remind Japan Trip - 5 months later")
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

    command_args = (" ".join(context.args)).split("-")

    if len(command_args) < 2:
        await commands.usage_string(message, remind)
        return

    title, target_time = command_args[0].strip(), command_args[1].strip()

    target_time = dateparser.parse(
        target_time, settings={"RETURN_AS_TIMEZONE_AWARE": True}
    )

    if target_time is None:
        await message.reply_text(
            "Invalid date/time format. Please provide a valid date and time."
        )
        return

    if target_time < datetime.datetime.now(target_time.tzinfo):
        await message.reply_text(
            "The specified time is in the past. Please provide a future date and time."
        )
        return

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
                target_time.timestamp(),
            ),
        )
        await conn.commit()

    await message.reply_text(
        text=f"I will remind you about <code>{title}</code> on {target_time.strftime('%B %d, %Y at %I:%M%p %Z')}",
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
        text = f"⏰ <code>{reminder['title']}</code>\n\n@{await utils.get_username(reminder['user_id'], context)}"
        await context.bot.send_message(
            reminder["chat_id"], text, parse_mode=ParseMode.HTML
        )
