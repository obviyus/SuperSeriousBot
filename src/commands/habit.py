import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import commands
import utils
from config import logger
from config.db import get_db
from utils.decorators import description, example, triggers, usage


async def fetch_habit_data(habit_id: int):
    async with get_db() as conn:
        async with conn.execute(
            """
                SELECT h.*, hm.user_id,
                       (SELECT COUNT(*) FROM habit_log hl
                        WHERE hl.habit_id = h.id
                        AND hl.user_id = hm.user_id
                        AND hl.create_time >= DATETIME('now', 'weekday 0', 'start of day', '-6 days')
                       ) AS week_count
                FROM habit h
                JOIN habit_members hm ON h.id = hm.habit_id
                WHERE h.id = ?
                """,
            (habit_id,),
        ) as cursor:
            return await cursor.fetchall()


async def habit_message_builder(
    habit_id: int, context: ContextTypes.DEFAULT_TYPE
) -> str:
    rows = await fetch_habit_data(habit_id)
    if not rows:
        return "Habit not found."

    habit_row = rows[0]
    text = f"📅 #{habit_row['habit_name']} 📅\n"

    for row in rows:
        user_count = row["week_count"]
        user_goal = habit_row["weekly_goal"]
        status_emoji = (
            "🚀" if user_count > user_goal else "⌛" if user_count < user_goal else "✅"
        )
        text += f"\n- {status_emoji} {user_count}/{user_goal} @{await utils.string.get_username(row['user_id'], context)}"
    return text


async def habit_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📅 Check-in", callback_data=f"hb:checkin,{habit_id}"
                )
            ],
            [InlineKeyboardButton("❌ Leave", callback_data=f"hb:leave,{habit_id}")],
        ]
    )


async def habit_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    action, habit_id = query.data.replace("hb:", "").split(",")

    async with get_db(write=True) as conn:
        try:
            if action == "checkin":
                await handle_check_in(conn, habit_id, query)
            elif action == "leave":
                await handle_leave(conn, habit_id, query)
            else:
                await query.answer("Invalid action.")
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Error in habit_button_handler: {e!s}")
            await query.answer("An error occurred. Please try again.")
            return

    try:
        await query.edit_message_text(
            await habit_message_builder(habit_id, context),
            reply_markup=await habit_keyboard(habit_id),
        )
    except Exception as e:
        logger.error(f"Error updating message in habit_button_handler: {e!s}")


async def handle_check_in(conn, habit_id, query):
    member_check = await conn.execute(
        "SELECT 1 FROM habit_members WHERE habit_id = ? AND user_id = ?",
        (habit_id, query.from_user.id),
    )
    is_member = await member_check.fetchone()
    if not is_member:
        await conn.execute(
            "INSERT INTO habit_members (habit_id, user_id) VALUES (?, ?)",
            (habit_id, query.from_user.id),
        )
    today_check = await conn.execute(
        """
        SELECT 1 FROM habit_log
        WHERE habit_id = ? AND user_id = ? AND create_time > DATETIME('now', 'start of day')
        """,
        (habit_id, query.from_user.id),
    )
    already_checked_in = await today_check.fetchone()
    if already_checked_in:
        await query.answer("You have already checked in today.")
    else:
        await conn.execute(
            "INSERT INTO habit_log (habit_id, user_id) VALUES (?, ?)",
            (habit_id, query.from_user.id),
        )
        await query.answer("Checked in successfully!")


async def handle_leave(conn, habit_id, query):
    await conn.execute(
        "DELETE FROM habit_members WHERE habit_id = ? AND user_id = ?",
        (habit_id, query.from_user.id),
    )
    await query.answer("You've left the habit.")


async def worker_habit_tracker(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_db() as conn:
        async with conn.execute(
            """
                SELECT * FROM habit
                WHERE id IN (SELECT DISTINCT habit_id FROM habit_members)
                """
        ) as cursor:
            group_habits = await cursor.fetchall()

    message_tasks = []
    for group_habit in group_habits:
        try:
            task = context.bot.send_message(
                chat_id=group_habit["chat_id"],
                text=await habit_message_builder(group_habit["id"], context),
                reply_markup=await habit_keyboard(group_habit["id"]),
            )
            message_tasks.append(task)
        except Exception as e:
            logger.error(f"Error sending message for habit {group_habit['id']}: {e!s}")

    await asyncio.gather(*message_tasks)


@triggers(["habit", "hb"])
@usage("/habit [HABIT_NAME] [DAYS_PER_WEEK]")
@description("Create a new habit to track in this group.")
@example("/habit workout 5")
async def habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 2:
        await commands.usage_string(update.message, habit)
        return

    habit_name, days_per_week = context.args[0], int(context.args[1])
    if not 1 <= days_per_week <= 7:
        await update.message.reply_text("Please enter a number between 1 and 7.")
        return

    async with get_db(write=True) as conn:
        async with conn.execute(
            "SELECT * FROM habit WHERE chat_id = ? AND habit_name = ?",
            (update.effective_chat.id, habit_name),
        ) as cursor:
            habit_exists = await cursor.fetchone()

        if habit_exists:
            await conn.execute(
                "INSERT OR IGNORE INTO habit_members (habit_id, user_id) VALUES (?, ?)",
                (habit_exists["id"], update.message.from_user.id),
            )
            await conn.commit()
            await update.message.reply_text(
                "A habit with this name already exists in this group. Adding you to it..."
            )
        else:
            await conn.execute(
                "INSERT INTO habit (chat_id, habit_name, weekly_goal, creator_id) VALUES (?, ?, ?, ?)",
                (
                    update.effective_chat.id,
                    habit_name,
                    days_per_week,
                    update.message.from_user.id,
                ),
            )
            habit_id = conn.lastrowid
            await conn.execute(
                "INSERT INTO habit_members (habit_id, user_id) VALUES (?, ?)",
                (habit_id, update.message.from_user.id),
            )
            await conn.commit()
            await update.message.reply_text(
                f"Created a new habit #{habit_name} with a goal of {days_per_week} days per week."
            )
            habit_exists = {"id": habit_id}

    await update.message.reply_text(
        await habit_message_builder(habit_exists["id"], context),
        reply_markup=await habit_keyboard(habit_exists["id"]),
    )
