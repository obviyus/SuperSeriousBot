from datetime import datetime

from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage

summon_log = {}


async def get_group_members(group_id: int, context: CallbackContext) -> list:
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT user_id FROM summon_group_members WHERE group_id = ?
        """,
        (group_id,),
    )

    return [
        f"@{await utils.get_username(user_id, context)}"
        for user_id, in cursor.fetchall()
    ]


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
            ],
            [
                InlineKeyboardButton(
                    "🔁 Resummon", callback_data=f"sg:resummon,{group_id}"
                )
            ],
        ],
    )


async def summon_keyboard_button(update: Update, context: CallbackContext) -> None:
    """Handle button for summon group."""
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
                INSERT INTO summon_group_members (group_id, user_id) VALUES (?, ?)
                """,
                (group_id, query.from_user.id),
            )
            await query.answer(f"Joined group.")
    elif action == "leave":
        if result:
            cursor.execute(
                """
                DELETE FROM summon_group_members WHERE group_id = ? AND user_id = ?
                """,
                (group_id, query.from_user.id),
            )
            await query.answer(f"Left group.")
        else:
            await query.answer("You are not a part of this group.")
    elif action == "resummon":
        last_tag_time = summon_log.get(int(group_id))
        if last_tag_time and (datetime.now() - last_tag_time).seconds < 60:
            await query.answer("You can only resummon once every 60 seconds.")
            return

        await query.answer("Resummoning...")
        members = await get_group_members(group_id, context)

        if members:
            for idx in range(0, len(members), 5):
                chunk = members[idx : idx + 5]

                await context.bot.send_message(
                    query.message.chat_id,
                    " ".join(chunk),
                    reply_markup=await summon_keyboard(group_id),
                    parse_mode=ParseMode.HTML,
                )
            summon_log[int(group_id)] = datetime.now()
            return
        else:
            await context.bot.send_message(
                query.message.chat_id,
                "No users in this group.",
                reply_markup=await summon_keyboard(group_id),
            )
            return

    current_group_members = await get_group_members(group_id, context)
    await update.effective_message.edit_text(
        " ".join(current_group_members)
        if current_group_members
        else "No members in group.",
        reply_markup=await summon_keyboard(group_id),
    )


@usage("/summon [GROUP_NAME]")
@example("/summon SwitchPlayers")
@triggers(["summon"])
@description("Tag users present in a group of tags. Join by using keyboard buttons.")
async def summon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tag users present in a group in a chat."""
    if len(context.args) == 0:
        await commands.usage_string(update.message, summon)
        return

    group_name = context.args[0].lower()
    cursor = sqlite_conn.cursor()

    cursor.execute(
        """
        SELECT summon_group_members.user_id, summon_groups.id FROM summon_groups 
        LEFT JOIN summon_group_members ON summon_groups.id = summon_group_members.group_id
        WHERE group_name = ? COLLATE NOCASE AND chat_id = ?
        """,
        (group_name, update.message.chat_id),
    )

    result = cursor.fetchall()
    filtered_row = []
    for row in result:
        # Check if user_id is still in the group
        check = await context.bot.get_chat_member(update.message.chat_id, row[0])
        if check.status == ChatMember.LEFT or check.status == ChatMember.BANNED:
            cursor.execute(
                """
                DELETE FROM summon_group_members WHERE group_id = ? AND user_id = ?
                """,
                (row[1], row[0]),
            )
            continue

        filtered_row.append(row)

    result = filtered_row

    if result:
        if not result[0]["user_id"]:
            await update.message.reply_text(
                "No users in this group.",
                reply_markup=await summon_keyboard(result[0]["id"]),
                parse_mode=ParseMode.HTML,
            )
            return

        for idx in range(0, len(result), 5):
            chunk = result[idx : idx + 5]

            await update.message.reply_text(
                " ".join(
                    [
                        f"@{await utils.get_username(user['user_id'], context)}"
                        for user in chunk
                    ]
                )
                if result[0]["user_id"]
                else "No users in this group.",
                reply_markup=await summon_keyboard(result[0]["id"]),
                parse_mode=ParseMode.HTML,
            )
            summon_log[result[0]["id"]] = datetime.now()
    else:
        cursor = sqlite_conn.cursor()

        cursor.execute(
            """INSERT INTO summon_groups (group_name, chat_id, creator_id) VALUES (?, ?, ?)""",
            (
                group_name.lower(),
                update.message.chat_id,
                update.message.from_user.id,
            ),
        )

        group_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO summon_group_members (group_id, user_id) VALUES (?, ?)""",
            (
                group_id,
                update.message.from_user.id,
            ),
        )

        await update.message.reply_text(
            f"Group <code>{group_name}</code> created. Tag all users in it using <code>/summon {group_name}</code>.",
            reply_markup=await summon_keyboard(group_id),
            parse_mode=ParseMode.HTML,
        )
