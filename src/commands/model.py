from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from config.options import config
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message

# AIDEV-NOTE: Global AI model setting uses chat_id = -1 in group_settings table
GLOBAL_CHAT_ID = -1

# AIDEV-NOTE: Default models for each command
DEFAULT_MODELS = {
    "ask": "openrouter/x-ai/grok-4-fast",
    "edit": "openrouter/google/gemini-2.5-flash-image-preview",
    "tr": "google/gemini-2.5-flash",
    "tldr": "openrouter/x-ai/grok-4-fast",
}

VALID_COMMANDS = {"ask", "edit", "tr", "tldr", "all"}

# AIDEV-NOTE: Valid thinking levels for OpenRouter reasoning tokens
# See: https://openrouter.ai/docs/use-cases/reasoning-tokens
VALID_THINKING_LEVELS = {"none", "minimal", "low", "medium", "high"}
DEFAULT_THINKING_LEVEL = "none"


async def get_model(command: str) -> str:
    """Get configured model for a command, falling back to default."""
    column = f"{command}_model"
    async with get_db() as conn:
        async with conn.execute(
            f"SELECT {column} FROM group_settings WHERE chat_id = ?",
            (GLOBAL_CHAT_ID,),
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] else DEFAULT_MODELS[command]


async def get_thinking() -> str:
    """Get configured thinking level for ask command, falling back to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT ask_thinking FROM group_settings WHERE chat_id = ?",
            (GLOBAL_CHAT_ID,),
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] else DEFAULT_THINKING_LEVEL


@triggers(["model"])
@usage("/model [command] [model_name]")
@example("/model ask openrouter/google/gemini-2.0-flash-thinking-exp-1219:free")
@description("Set AI models for commands: ask, caption, edit, tr, or all (admin only)")
async def model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not update.effective_user:
        return
    # Check if user is admin
    if str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]:
        await message.reply_text("❌ This command is only available to admins.")
        return

    if not context.args:
        # Show current models for all commands
        async with get_db() as conn:
            async with conn.execute(
                "SELECT ask_model, edit_model, tr_model, tldr_model FROM group_settings WHERE chat_id = ?",
                (GLOBAL_CHAT_ID,),
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    ask_model = result[0] or DEFAULT_MODELS["ask"]
                    edit_model = result[1] or DEFAULT_MODELS["edit"]
                    tr_model = result[2] or DEFAULT_MODELS["tr"]
                    tldr_model = result[3] or DEFAULT_MODELS["tldr"]
                else:
                    ask_model = DEFAULT_MODELS["ask"]
                    edit_model = DEFAULT_MODELS["edit"]
                    tr_model = DEFAULT_MODELS["tr"]
                    tldr_model = DEFAULT_MODELS["tldr"]

        text = "📋 <b>Current AI Models:</b>\n\n"
        text += f"• <b>/ask</b>: <code>{ask_model}</code>\n"
        text += f"• <b>/edit</b>: <code>{edit_model}</code>\n"
        text += f"• <b>/tr</b>: <code>{tr_model}</code>\n"
        text += f"• <b>/tldr</b>: <code>{tldr_model}</code>\n\n"
        text += "<b>Usage:</b> <code>/model &lt;command&gt; &lt;model_name&gt;</code>\n"
        text += "<b>Commands:</b> ask, edit, tr, tldr, all\n\n"
        text += "<b>Examples:</b>\n"
        text += "• <code>/model ask openrouter/google/gemini-3.0-flash</code>\n"
        text += "• <code>/model all openrouter/anthropic/claude-3.5-sonnet</code>"

        await message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )
        return

    if len(context.args) < 2:
        await message.reply_text(
            "❌ Please specify both command and model name.\n"
            "Usage: <code>/model &lt;command&gt; &lt;model_name&gt;</code>\n"
            "Commands: ask, caption, edit, tr, all",
            parse_mode=ParseMode.HTML,
        )
        return

    command = context.args[0].lower()
    new_model = " ".join(context.args[1:])

    if command not in VALID_COMMANDS:
        await message.reply_text(
            f"❌ Invalid command: <code>{command}</code>\n"
            "Valid commands: ask, caption, edit, tr, all",
            parse_mode=ParseMode.HTML,
        )
        return

    async with get_db() as conn:
        if command == "all":
            # Update all models to the same value
            await conn.execute(
                """
                INSERT INTO group_settings (chat_id, ask_model, edit_model, tr_model, tldr_model)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    ask_model = excluded.ask_model,
                    edit_model = excluded.edit_model,
                    tr_model = excluded.tr_model,
                    tldr_model = excluded.tldr_model
                """,
                (GLOBAL_CHAT_ID, new_model, new_model, new_model, new_model),
            )
            response_text = (
                f"✅ All command models updated to: <code>{new_model}</code>"
            )
        else:
            # Update specific command model
            column_name = f"{command}_model"
            await conn.execute(
                f"""
                INSERT INTO group_settings (chat_id, {column_name})
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET {column_name} = excluded.{column_name}
                """,
                (GLOBAL_CHAT_ID, new_model),
            )
            response_text = (
                f"✅ Model for <b>/{command}</b> updated to: <code>{new_model}</code>"
            )

        await conn.commit()

    await message.reply_text(
        response_text,
        parse_mode=ParseMode.HTML,
    )


@triggers(["thinking"])
@usage("/thinking [level]")
@example("/thinking high")
@description("Set thinking level for /ask: none, minimal, low, medium, high (admin only)")
async def thinking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not update.effective_user:
        return

    # Check if user is admin
    if str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]:
        await message.reply_text("❌ This command is only available to admins.")
        return

    if not context.args:
        # Show current thinking level
        current_level = await get_thinking()
        text = "🧠 <b>OpenRouter Thinking Level</b>\n\n"
        text += f"Current level: <code>{current_level}</code>\n\n"
        text += "<b>Available levels:</b>\n"
        text += "• <code>none</code> - No reasoning tokens\n"
        text += "• <code>minimal</code> - Minimal reasoning\n"
        text += "• <code>low</code> - Low reasoning effort\n"
        text += "• <code>medium</code> - Medium reasoning effort\n"
        text += "• <code>high</code> - High reasoning effort\n\n"
        text += "<b>Usage:</b> <code>/thinking &lt;level&gt;</code>"

        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    new_level = context.args[0].lower()

    if new_level not in VALID_THINKING_LEVELS:
        await message.reply_text(
            f"❌ Invalid thinking level: <code>{new_level}</code>\n"
            "Valid levels: none, minimal, low, medium, high",
            parse_mode=ParseMode.HTML,
        )
        return

    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, ask_thinking)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET ask_thinking = excluded.ask_thinking
            """,
            (GLOBAL_CHAT_ID, new_level),
        )
        await conn.commit()

    await message.reply_text(
        f"✅ Thinking level updated to: <code>{new_level}</code>",
        parse_mode=ParseMode.HTML,
    )
