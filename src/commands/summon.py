from datetime import datetime

from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from config.db import get_db
from utils.decorators import description, example, triggers, usage

summon_log = {}


async def get_group_members(group_id: int, context: CallbackContext) -> list:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT user_id, chat_id
            FROM summon_group_members
                JOIN summon_groups ON summon_groups.id = summon_group_members.group_id
            WHERE group_id = ?;
            """,
            (group_id,),
        ) as cursor:
            group_members = [(row[0], row[1]) for row in await cursor.fetchall()]

    members = []
    for user_id, chat_id in group_members:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in [ChatMember.LEFT, ChatMember.BANNED]:
                username = await utils.get_username(user_id, context)
                if username:
                    members.append(f"@{username}")
        except Exception as e:
            print(f"Error getting member {user_id}: {e}")

    return members


async def summon_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Join", callback_data=f"sg:join,{group_id}"),
                InlineKeyboardButton("❌ Leave", callback_data=f"sg:leave,{group_id}"),
            ],
            [
                InlineKeyboardButton(
                    "🔁 Resummon", callback_data=f"sg:resummon,{group_id}"
                )
            ],
        ]
    )


async def send_chunked_messages(
    chat_id: int, members: list, context: ContextTypes.DEFAULT_TYPE, group_id: int
):
    if not members:
        await context.bot.send_message(
            chat_id,
            "No users in this group.",
            reply_markup=await summon_keyboard(group_id),
            parse_mode=ParseMode.HTML,
        )
        return

    for idx in range(0, len(members), 5):
        chunk = members[idx : idx + 5]
        await context.bot.send_message(
            chat_id, " ".join(chunk), parse_mode=ParseMode.HTML
        )

    await context.bot.send_message(
        chat_id,
        "Use the buttons below to join or leave the group:",
        reply_markup=await summon_keyboard(group_id),
        parse_mode=ParseMode.HTML,
    )


async def summon_keyboard_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    action, group_id = query.data.replace("sg:", "").split(",")
    group_id = int(group_id)

    async with get_db(write=True) as conn:
        if action == "join":
            await conn.execute(
                """
                INSERT INTO summon_group_members (group_id, user_id)
                VALUES (?, ?)
                ON CONFLICT (group_id, user_id) DO NOTHING
                """,
                (group_id, query.from_user.id),
            )
            await conn.commit()
            await query.answer("Joined group.")
            return
        elif action == "leave":
            await conn.execute(
                "DELETE FROM summon_group_members WHERE group_id = ? AND user_id = ?",
                (group_id, query.from_user.id),
            )
            await conn.commit()
            await query.answer("Left group.")
            return
        elif action == "resummon":
            last_tag_time = summon_log.get(group_id)
            if last_tag_time and (datetime.now() - last_tag_time).seconds < 60:
                await query.answer("You can only resummon once every 60 seconds.")
                return

            await query.answer("Resummoning...")
            members = await get_group_members(group_id, context)
            await send_chunked_messages(
                query.message.chat_id, members, context, group_id
            )
            summon_log[group_id] = datetime.now()
            return


async def get_or_create_group(conn, group_name, chat_id, user_id):
    async with conn.execute(
        "SELECT id FROM summon_groups WHERE group_name = ? COLLATE NOCASE AND chat_id = ?",
        (group_name, chat_id),
    ) as cursor:
        result = await cursor.fetchone()

    if result:
        return result[0]

    async with conn.execute(
        "INSERT INTO summon_groups (group_name, chat_id, creator_id) VALUES (?, ?, ?)",
        (group_name, chat_id, user_id),
    ) as cursor:
        await conn.commit()
        group_id = cursor.lastrowid

    await conn.execute(
        "INSERT INTO summon_group_members (group_id, user_id) VALUES (?, ?)",
        (group_id, user_id),
    )
    await conn.commit()
    return group_id


@usage("/summon [GROUP_NAME]")
@example("/summon SwitchPlayers")
@triggers(["summon"])
@description("Tag users present in a group of tags. Join by using keyboard buttons.")
async def summon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        await update.message.reply_text("This command can only be used in group chats.")
        return

    if not context.args:
        await commands.usage_string(update.message, summon)
        return

    group_name = context.args[0].lower()

    async with get_db(write=True) as conn:
        group_id = await get_or_create_group(
            conn, group_name, update.effective_chat.id, update.effective_user.id
        )

    members = await get_group_members(group_id, context)
    await send_chunked_messages(update.effective_chat.id, members, context, group_id)
    summon_log[group_id] = datetime.now()
