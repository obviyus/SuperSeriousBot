from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from utils.admin import is_admin
from utils.decorators import description, example, triggers, usage

WHITELIST_TYPE = "chat"


def _normalize_command(command: str) -> str:
    command = command.lstrip("/").strip().lower()
    return command


def _resolve_chat_id(update: Update, args: list[str]) -> int | None:
    if len(args) > 1:
        try:
            return int(args[1])
        except ValueError:
            return None
    if update.effective_chat:
        return update.effective_chat.id
    return None


@triggers(["whitelist"])
@usage("/whitelist <command> [chat_id]")
@example("/whitelist tr -1001234567890")
@description("Allow a chat to use a command (admins only)")
async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only available to admins")
        return

    if not context.args:
        await commands.usage_string(message, whitelist_command)
        return

    command_name = _normalize_command(context.args[0])
    if not command_name:
        await update.message.reply_text("Please provide a command to whitelist.")
        return

    chat_id = _resolve_chat_id(update, context.args)
    if chat_id is None:
        await update.message.reply_text(
            "Could not determine target chat. Provide a chat ID explicitly."
        )
        return

    async with get_db(write=True) as conn:
        async with conn.execute(
            """
            SELECT 1 FROM command_whitelist
            WHERE command = ? AND whitelist_type = ? AND whitelist_id = ?
            """,
            (command_name, WHITELIST_TYPE, chat_id),
        ) as cursor:
            exists = await cursor.fetchone()

        if exists:
            await update.message.reply_text(
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
        await conn.commit()

    await update.message.reply_text(
        f"✅ Added chat <code>{chat_id}</code> to the whitelist for /{command_name}",
        parse_mode=ParseMode.HTML,
    )


@triggers(["unwhitelist"])
@usage("/unwhitelist <command> [chat_id]")
@example("/unwhitelist tr -1001234567890")
@description("Remove a chat from a command whitelist (admins only)")
async def unwhitelist_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = update.message
    if not message:
        return

    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only available to admins")
        return

    if not context.args:
        await commands.usage_string(message, unwhitelist_command)
        return

    command_name = _normalize_command(context.args[0])
    if not command_name:
        await update.message.reply_text("Please provide a command to unwhitelist.")
        return

    chat_id = _resolve_chat_id(update, context.args)
    if chat_id is None:
        await update.message.reply_text(
            "Could not determine target chat. Provide a chat ID explicitly."
        )
        return

    async with get_db(write=True) as conn:
        result = await conn.execute(
            """
            DELETE FROM command_whitelist
            WHERE command = ? AND whitelist_type = ? AND whitelist_id = ?
            """,
            (command_name, WHITELIST_TYPE, chat_id),
        )
        await conn.commit()

    if result.rowcount:
        await update.message.reply_text(
            f"✅ Removed chat <code>{chat_id}</code> from /{command_name}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"❓ Chat <code>{chat_id}</code> was not whitelisted for /{command_name}",
            parse_mode=ParseMode.HTML,
        )
