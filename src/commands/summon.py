import asyncio
from datetime import datetime

from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import KeyboardButtonStyle, ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from config.db import get_db
from utils.decorators import command
from utils.messages import get_message

summon_log = {}


async def perform_summon(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    group_id: int,
    group_name: str,
):
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

    async def check_member(user_id: int, member_chat_id: int) -> str | None:
        try:
            member = await context.bot.get_chat_member(member_chat_id, user_id)
            if member.status not in [ChatMember.LEFT, ChatMember.BANNED]:
                username = await utils.get_username(user_id, context)
                if username:
                    return f"@{username}"
        except Exception as e:
            print(f"Error getting member {user_id}: {e}")
        return None

    members = [
        member
        for member in await asyncio.gather(
            *(check_member(user_id, member_chat_id) for user_id, member_chat_id in group_members)
        )
        if member
    ]
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Join",
                    callback_data=f"sg:join,{group_id}",
                    style=KeyboardButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    "❌ Leave",
                    callback_data=f"sg:leave,{group_id}",
                    style=KeyboardButtonStyle.DANGER,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔁 Resummon",
                    callback_data=f"sg:resummon,{group_id}",
                    style=KeyboardButtonStyle.PRIMARY,
                )
            ],
        ]
    )

    if not members:
        await context.bot.send_message(
            chat_id,
            f"No users in group '{group_name}'.",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        summon_log[group_id] = datetime.now()
        return

    for index in range(0, len(members), 5):
        chunk = members[index : index + 5]
        await context.bot.send_message(
            chat_id,
            f"[{group_name}] ({len(members)} members) {' '.join(chunk)}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard if index + 5 >= len(members) else None,
        )

    summon_log[group_id] = datetime.now()


async def summon_keyboard_button(update: Update, context: CallbackContext) -> None:
    message = get_message(update)

    if not message:
        return
    query = update.callback_query
    if not query or not query.data or not query.from_user or not query.message:
        return

    action, group_id_str = query.data.replace("sg:", "").split(",")
    group_id = int(group_id_str)

    async with get_db() as conn:
        if action == "join":
            await conn.execute(
                """
                INSERT INTO summon_group_members (group_id, user_id)
                VALUES (?, ?)
                ON CONFLICT (group_id, user_id) DO NOTHING
                """,
                (group_id, query.from_user.id),
            )
            await query.answer("Joined group.")
            return
        elif action == "leave":
            await conn.execute(
                "DELETE FROM summon_group_members WHERE group_id = ? AND user_id = ?",
                (group_id, query.from_user.id),
            )
            await query.answer("Left group.")
            return
        elif action == "resummon":
            last_tag_time = summon_log.get(group_id)
            if last_tag_time and (datetime.now() - last_tag_time).seconds < 60:
                remaining_seconds = 60 - (datetime.now() - last_tag_time).seconds
                await query.answer(
                    f"You can only resummon once every 60 seconds. Wait {remaining_seconds}s."
                )
                return

            await query.answer("Resummoning...")
            async with get_db() as conn:
                async with conn.execute(
                    "SELECT group_name FROM summon_groups WHERE id = ?", (group_id,)
                ) as cursor:
                    result = await cursor.fetchone()
                    group_name = result[0] if result else "Unknown"

            await perform_summon(context, message.chat_id, group_id, group_name)
            return


@command(
    triggers=["summon"],
    usage="/summon [GROUP_NAME]",
    example="/summon SwitchPlayers",
    description="Tag users present in a group of tags. Join by using keyboard buttons.",
)
async def summon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not update.effective_chat or not update.effective_user:
        return

    if update.effective_chat.type == "private":
        await message.reply_text("This command can only be used in group chats.")
        return

    if not context.args:
        await commands.usage_string(message, summon)
        return

    group_name = context.args[0].lower()

    async with get_db() as conn:
        async with conn.execute(
            "SELECT id FROM summon_groups WHERE group_name = ? COLLATE NOCASE AND chat_id = ?",
            (group_name, update.effective_chat.id),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            group_id = result[0]
        else:
            cursor = await conn.execute(
                "INSERT INTO summon_groups (group_name, chat_id, creator_id) VALUES (?, ?, ?)",
                (group_name, update.effective_chat.id, update.effective_user.id),
            )
            group_id = cursor.lastrowid
            if group_id is None:
                raise RuntimeError("Failed to create summon group.")
            await conn.execute(
                "INSERT INTO summon_group_members (group_id, user_id) VALUES (?, ?)",
                (group_id, update.effective_user.id),
            )

    await perform_summon(context, update.effective_chat.id, group_id, group_name)
