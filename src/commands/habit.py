import asyncio
import sqlite3

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

import commands
import utils
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


async def habit_message_builder(
    habit_id: int, context: ContextTypes.DEFAULT_TYPE
) -> str:
    """Build the message for the habit."""
    cursor = sqlite_conn.cursor()

    cursor.execute(
        """
        SELECT * FROM habit 
        WHERE id = ?
        """,
        (habit_id,),
    )

    habit_row = cursor.fetchone()
    if not habit_row:
        return "Habit not found."

    cursor.execute(
        """
        SELECT * FROM habit_members
        WHERE habit_id = ?
        """,
        (habit_id,),
    )

    habit_members = cursor.fetchall()

    text = f"📅 #{habit_row['habit_name']} 📅\n"

    for habit_logged in habit_members:
        cursor.execute(
            """
            SELECT user_id, COUNT(*) AS week_count
            FROM habit_log
            WHERE habit_id = ? 
                AND create_time >= DATETIME('now', 'weekday 0', 'start of day', '-6 days')
                AND user_id = ?
            """,
            (habit_id, habit_logged["user_id"]),
        )

        user_count = cursor.fetchone()["week_count"]
        user_goal = habit_row["weekly_goal"]
        status_emoji = (
            "🚀" if user_count > user_goal else "⌛" if user_count < user_goal else "✅"
        )

        text += (
            f"\n- {status_emoji} {user_count}/{user_goal} "
            f"@{await utils.string.get_username(habit_logged['user_id'], context)}"
        )

    return text


async def habit_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📅 Check-in",
                    callback_data=f"hb:checkin,{habit_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Leave",
                    callback_data=f"hb:leave,{habit_id}",
                ),
            ],
        ],
    )


async def habit_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle button for habit."""
    query = update.callback_query
    action, habit_id = query.data.replace("hb:", "").split(",")

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM habit_members WHERE habit_id = ? AND user_id = ?
        """,
        (habit_id, query.from_user.id),
    )

    result = cursor.fetchone()

    if action == "checkin":
        if not result:
            cursor.execute(
                """
                INSERT INTO habit_members (habit_id, user_id) VALUES (?, ?)
                """,
                (habit_id, query.from_user.id),
            )

        # Check if user has already checked in today
        cursor.execute(
            """
            SELECT * FROM habit_log WHERE habit_id = ? AND user_id = ? AND create_time > DATETIME('now', 'start of day')
            """,
            (habit_id, query.from_user.id),
        )

        if cursor.fetchone():
            await query.answer("You have already checked in today.")
            await query.edit_message_text(
                await habit_message_builder(habit_id, context),
                reply_markup=await habit_keyboard(habit_id),
            )
            return

        cursor.execute(
            """
            INSERT INTO habit_log (habit_id, user_id) VALUES (?, ?)
            """,
            (habit_id, query.from_user.id),
        )
    else:
        if not result:
            await query.answer("You are not a member of this habit.")
            return

        cursor.execute(
            """
            DELETE FROM habit_members WHERE habit_id = ? AND user_id = ?
            """,
            (habit_id, query.from_user.id),
        )

    await query.edit_message_text(
        await habit_message_builder(habit_id, context),
        reply_markup=await habit_keyboard(habit_id),
    )


async def worker_habit_tracker(context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all habits with > 0 members and send daily message."""
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM habit WHERE (SELECT COUNT(*) FROM habit_members WHERE habit_id = habit.id) > 0
        """
    )

    message_tasks = []

    group_habits = cursor.fetchall()
    for group_habit in group_habits:
        message_tasks.append(
            context.bot.send_message(
                chat_id=group_habit["chat_id"],
                text=await habit_message_builder(group_habit["id"], context),
                reply_markup=await habit_keyboard(group_habit["id"]),
            )
        )

    await asyncio.gather(*message_tasks)


@triggers(["habit", "hb"])
@usage("/habit [HABIT_NAME] [DAYS_PER_WEEK]")
@description("Create a new habit to track in this group.")
@example("/habit workout 5")
async def habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new habit to track in this group."""
    if not context.args:
        await commands.usage_string(update.message, habit)
        return

    if len(context.args) == 1:
        await update.message.reply_text("Please enter a habit name and days per week.")
        return

    days_per_week = int(context.args[1])
    if days_per_week < 1 or days_per_week > 7:
        await update.message.reply_text("Please enter a number between 1 and 7.")
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT * FROM habit WHERE chat_id = ? AND habit_name = ?",
        (update.effective_chat.id, context.args[0]),
    )
    habit_exists = cursor.fetchone()

    if habit_exists:
        await update.message.reply_text(
            "A habit with this name already exists in this group. Adding you to it..."
        )

        try:
            cursor.execute(
                "INSERT INTO habit_members (habit_id, user_id) VALUES (?, ?)",
                (habit_exists["id"], update.message.from_user.id),
            )
        except sqlite3.IntegrityError:
            pass

        await update.message.reply_text(
            await habit_message_builder(habit_exists["id"], context),
            reply_markup=await habit_keyboard(habit_exists["id"]),
        )
        return

    cursor.execute(
        "INSERT INTO habit (chat_id, habit_name, weekly_goal, creator_id) VALUES (?, ?, ?, ?)",
        (
            update.effective_chat.id,
            context.args[0],
            days_per_week,
            update.message.from_user.id,
        ),
    )

    habit_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO habit_members (habit_id, user_id) VALUES (?, ?)",
        (habit_id, update.message.from_user.id),
    )

    await update.message.reply_text(
        f"Created a new habit #{context.args[0]} with a goal of {days_per_week} days per week."
    )

    await update.message.reply_text(
        await habit_message_builder(habit_id, context),
        reply_markup=await habit_keyboard(habit_id),
    )
