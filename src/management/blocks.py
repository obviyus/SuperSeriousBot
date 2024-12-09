from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils.admin import is_admin
from utils.decorators import description, example, triggers, usage


@usage("/block <user_id> <command>")
@example("/block 123456 weather")
@triggers(["block"])
@description("Block a user from using specific commands")
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only available to admins")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /block <user_id> <command>")
        return

    try:
        user_id = int(context.args[0])
        command = context.args[1].lower()

        async with get_db(write=True) as conn:
            await conn.execute(
                """
                INSERT INTO command_blocklist (user_id, command, blocked_by)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, command) DO NOTHING
                """,
                (user_id, command, update.effective_user.id),
            )
            await conn.commit()

        await update.message.reply_text(
            f"✅ User <code>{user_id}</code> blocked from using /{command}",
            parse_mode=ParseMode.HTML,
        )

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


@usage("/unblock <user_id> <command>")
@example("/unblock 123456 weather")
@triggers(["unblock"])
@description("Unblock a user from using specific commands")
async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only available to admins")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /unblock <user_id> <command>")
        return

    try:
        user_id = int(context.args[0])
        command = context.args[1].lower()

        async with get_db(write=True) as conn:
            result = await conn.execute(
                "DELETE FROM command_blocklist WHERE user_id = ? AND command = ?",
                (user_id, command),
            )
            await conn.commit()

            if result.rowcount > 0:
                await update.message.reply_text(
                    f"✅ User <code>{user_id}</code> unblocked from /{command}",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text(
                    f"❓ User <code>{user_id}</code> was not blocked from /{command}",
                    parse_mode=ParseMode.HTML,
                )

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


@usage("/blocklist")
@example("/blocklist")
@triggers(["blocklist"])
@description("Show all blocked users and their blocked commands")
async def show_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only available to admins")
        return

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT user_id, command, blocked_by, blocked_at
            FROM command_blocklist
            ORDER BY blocked_at DESC
            """
        ) as cursor:
            blocks = await cursor.fetchall()

    if not blocks:
        await update.message.reply_text("No blocked users found.")
        return

    text = "🚫 <b>Command Blocklist:</b>\n\n"
    for block in blocks:
        text += (
            f"User: <code>{block['user_id']}</code>\n"
            f"Command: /{block['command']}\n"
            f"Blocked by: <code>{block['blocked_by']}</code>\n"
            f"When: {block['blocked_at']}\n\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
