from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from utils.admin import is_admin
from utils.decorators import command
from utils.messages import get_message

WHITELIST_TYPE = "chat"


async def _update_whitelist(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    handler,
    *,
    remove: bool,
) -> None:
    message = get_message(update)
    if not message:
        return
    if not update.effective_user or not is_admin(update.effective_user.id):
        await message.reply_text("❌ This command is only available to admins")
        return
    if not context.args:
        await commands.usage_string(message, handler)
        return

    command_name = context.args[0].lstrip("/").strip().lower()
    if not command_name:
        await message.reply_text(
            "Please provide a command to unwhitelist."
            if remove
            else "Please provide a command to whitelist."
        )
        return

    if len(context.args) > 1:
        try:
            chat_id = int(context.args[1])
        except ValueError:
            chat_id = None
    else:
        chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        await message.reply_text(
            "Could not determine target chat. Provide a chat ID explicitly."
        )
        return

    async with get_db() as conn:
        if remove:
            result = await conn.execute(
                """
                DELETE FROM command_whitelist
                WHERE command = ? AND whitelist_type = ? AND whitelist_id = ?
                """,
                (command_name, WHITELIST_TYPE, chat_id),
            )
        else:
            async with conn.execute(
                """
                SELECT 1 FROM command_whitelist
                WHERE command = ? AND whitelist_type = ? AND whitelist_id = ?
                """,
                (command_name, WHITELIST_TYPE, chat_id),
            ) as cursor:
                if await cursor.fetchone():
                    await message.reply_text(
                        f"✅ Chat <code>{chat_id}</code> is already whitelisted for /{command_name}",
                        parse_mode=ParseMode.HTML,
                    )
                    return
            await conn.execute(
                """
                INSERT INTO command_whitelist (command, whitelist_type, whitelist_id)
                VALUES (?, ?, ?)
                """,
                (command_name, WHITELIST_TYPE, chat_id),
            )

    if remove:
        await message.reply_text(
            (
                f"✅ Removed chat <code>{chat_id}</code> from /{command_name}"
                if result.rowcount
                else f"❓ Chat <code>{chat_id}</code> was not whitelisted for /{command_name}"
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    await message.reply_text(
        f"✅ Added chat <code>{chat_id}</code> to the whitelist for /{command_name}",
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["whitelist"],
    usage="/whitelist <command> [chat_id]",
    example="/whitelist tr -1001234567890",
    description="Allow a chat to use a command (admins only)",
)
async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _update_whitelist(update, context, whitelist_command, remove=False)


@command(
    triggers=["unwhitelist"],
    usage="/unwhitelist <command> [chat_id]",
    example="/unwhitelist tr -1001234567890",
    description="Remove a chat from a command whitelist (admins only)",
)
async def unwhitelist_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await _update_whitelist(update, context, unwhitelist_command, remove=True)
