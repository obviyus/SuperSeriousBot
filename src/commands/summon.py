from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


async def summon_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Join",
                    callback_data=f"sg:join,{group_id}",
                ),
                InlineKeyboardButton(
                    "❌ Leave",
                    callback_data=f"sg:leave,{group_id}",
                ),
            ]
        ],
    )


async def summon_keyboard_button(update: Update, context: CallbackContext) -> None:
    """Remove a TV show from the watchlist."""
    query = update.callback_query
    action, group_id = query.data.replace("sg:", "").split(",")

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM 'summon_group_members' WHERE group_id = ? AND user_id = ?
        """,
        (group_id, query.from_user.id),
    )

    result = cursor.fetchone()

    if action == "join":
        if result:
            await query.answer("You are already a part of this group.")
        else:
            cursor.execute(
                """
                INSERT INTO 'summon_group_members' (group_id, user_id) VALUES (?, ?)
                """,
                (group_id, query.from_user.id),
            )
            await query.answer(f"Joined group.")
    elif action == "leave":
        if result:
            cursor.execute(
                """
                DELETE FROM 'summon_group_members' WHERE group_id = ? AND user_id = ?
                """,
                (group_id, query.from_user.id),
            )
            await query.answer(f"Left group.")
        else:
            await query.answer("You are not a part of this group.")


@usage("/summon [GROUP_NAME]")
@example("/summon SwitchPlayers")
@triggers(["summon"])
@description("Tag users present in a group of tags. Join by using keyboard buttons.")
async def summon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tag users present in a group in a chat."""
    if len(context.args) == 0:
        await commands.usage_string(update.message, summon)
        return

    group_name = context.args[0]
    cursor = sqlite_conn.cursor()

    cursor.execute(
        """
        SELECT summon_group_members.user_id, summon_groups.id FROM summon_groups 
        LEFT JOIN summon_group_members ON summon_groups.id = summon_group_members.group_id
        WHERE group_name = ? AND chat_id = ? COLLATE NOCASE
        """,
        (group_name, update.message.chat_id),
    )

    result = cursor.fetchall()
    if result:
        await update.message.reply_text(
            " ".join(
                [
                    f"@{await utils.get_username(user['user_id'], context)}"
                    for user in result
                ]
            )
            if result[0]["user_id"]
            else "No users in this group.",
            reply_markup=await summon_keyboard(result[0]["id"]),
            parse_mode=ParseMode.HTML,
        )
    else:
        cursor.execute(
            """INSERT INTO summon_groups (group_name, chat_id, creator_id) VALUES (?, ?, ?)""",
            (
                group_name,
                update.message.chat_id,
                update.message.from_user.id,
            ),
        )

        cursor.execute(
            """INSERT INTO summon_group_members (group_id, user_id) VALUES (?, ?)""",
            (
                cursor.lastrowid,
                update.message.from_user.id,
            ),
        )

        await update.message.reply_text(
            f"Group <code>{group_name}</code> created. Tag all users in it using <code>/summon {group_name}</code>.",
            reply_markup=await summon_keyboard(group_name),
            parse_mode=ParseMode.HTML,
        )
