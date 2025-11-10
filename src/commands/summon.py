from datetime import datetime

from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from config.db import get_db
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message

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
    chat_id: int,
    members: list,
    context: ContextTypes.DEFAULT_TYPE,
    group_id: int,
    group_name: str,
):
    if not members:
        await context.bot.send_message(
            chat_id,
            f"No users in group '{group_name}'.",
            reply_markup=await summon_keyboard(group_id),
            parse_mode=ParseMode.HTML,
        )
        return

    for idx in range(0, len(members), 5):
        chunk = members[idx : idx + 5]
        await context.bot.send_message(
            chat_id,
            f"[{group_name}] ({len(members)} members) {' '.join(chunk)}",
            parse_mode=ParseMode.HTML,
        )

    await context.bot.send_message(
        chat_id,
        f"Use the buttons below to join or leave group '{group_name}' ({len(members)} members):",
        reply_markup=await summon_keyboard(group_id),
        parse_mode=ParseMode.HTML,
    )


async def summon_keyboard_button(update: Update, context: CallbackContext) -> None:
    message = get_message(update)

    if not message:
        return
    query = update.callback_query
    if not query or not query.data or not query.from_user or not query.message:
        return

    action, group_id_str = query.data.replace("sg:", "").split(",")
    group_id = int(group_id_str)

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
                remaining_seconds = 60 - (datetime.now() - last_tag_time).seconds
                await query.answer(
                    f"You can only resummon once every 60 seconds. Wait {remaining_seconds}s."
                )
                return

            await query.answer("Resummoning...")
            # Get group name for resummon
            async with get_db() as conn:
                async with conn.execute(
                    "SELECT group_name FROM summon_groups WHERE id = ?", (group_id,)
                ) as cursor:
                    result = await cursor.fetchone()
                    group_name = result[0] if result else "Unknown"

            members = await get_group_members(group_id, context)

            # query.message is guaranteed to be Message (not InaccessibleMessage) here
            from telegram import Message as TelegramMessage

            if isinstance(query.message, TelegramMessage):
                await send_chunked_messages(
                    query.message.chat_id, members, context, group_id, group_name
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

    async with get_db(write=True) as conn:
        group_id = await get_or_create_group(
            conn, group_name, update.effective_chat.id, update.effective_user.id
        )

    members = await get_group_members(group_id, context)
    await send_chunked_messages(
        update.effective_chat.id, members, context, group_id, group_name
    )
    summon_log[group_id] = datetime.now()
