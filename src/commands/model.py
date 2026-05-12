from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils.admin import is_admin
from utils.decorators import command
from utils.messages import get_message

GLOBAL_CHAT_ID = -1

DEFAULT_MODELS = {
    "ask": "openrouter/x-ai/grok-4-fast",
    "edit": "openrouter/google/gemini-2.5-flash-image-preview",
    "tr": "google/gemini-2.5-flash",
    "tldr": "openrouter/x-ai/grok-4-fast",
}
MODEL_COMMANDS = tuple(DEFAULT_MODELS)
MODEL_COMMAND_LIST = ", ".join((*MODEL_COMMANDS, "all"))
VALID_COMMANDS = {*MODEL_COMMANDS, "all"}

VALID_THINKING_LEVELS = {"none", "minimal", "low", "medium", "high"}
DEFAULT_THINKING_LEVEL = "none"


def normalize_model_name(model_name: str) -> str:
    return model_name.removeprefix("openrouter/")


async def get_model(command: str) -> str:
    column = f"{command}_model"
    async with get_db() as conn:
        async with conn.execute(
            f"SELECT {column} FROM group_settings WHERE chat_id = ?",
            (GLOBAL_CHAT_ID,),
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] else DEFAULT_MODELS[command]


async def get_thinking() -> str:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT ask_thinking FROM group_settings WHERE chat_id = ?",
            (GLOBAL_CHAT_ID,),
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] else DEFAULT_THINKING_LEVEL


@command(
    triggers=["model"],
    usage="/model [command] [model_name]",
    example="/model ask openrouter/google/gemini-2.0-flash-thinking-exp-1219:free",
    description=f"Set AI models for commands: {MODEL_COMMAND_LIST} (admin only)",
)
async def model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not update.effective_user or not is_admin(update.effective_user.id):
        await message.reply_text("❌ This command is only available to admins.")
        return

    if not context.args:
        columns = ", ".join(f"{name}_model" for name in MODEL_COMMANDS)
        async with get_db() as conn:
            async with conn.execute(
                f"SELECT {columns} FROM group_settings WHERE chat_id = ?",
                (GLOBAL_CHAT_ID,),
            ) as cursor:
                result = await cursor.fetchone()

        models = {
            name: (result[index] if result and result[index] else DEFAULT_MODELS[name])
            for index, name in enumerate(MODEL_COMMANDS)
        }
        text = "📋 <b>Current AI Models:</b>\n\n"
        text += "\n".join(
            f"• <b>/{name}</b>: <code>{models[name]}</code>" for name in MODEL_COMMANDS
        )
        text += "\n\n<b>Usage:</b> <code>/model &lt;command&gt; &lt;model_name&gt;</code>\n"
        text += f"<b>Commands:</b> {MODEL_COMMAND_LIST}\n\n"
        text += "<b>Examples:</b>\n"
        text += "• <code>/model ask openrouter/google/gemini-3.0-flash</code>\n"
        text += "• <code>/model all openrouter/anthropic/claude-3.5-sonnet</code>"
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if len(context.args) < 2:
        await message.reply_text(
            "❌ Please specify both command and model name.\n"
            "Usage: <code>/model &lt;command&gt; &lt;model_name&gt;</code>\n"
            f"Commands: {MODEL_COMMAND_LIST}",
            parse_mode=ParseMode.HTML,
        )
        return

    command = context.args[0].lower()
    new_model = " ".join(context.args[1:])

    if command not in VALID_COMMANDS:
        await message.reply_text(
            f"❌ Invalid command: <code>{command}</code>\n"
            f"Valid commands: {MODEL_COMMAND_LIST}",
            parse_mode=ParseMode.HTML,
        )
        return

    updated_commands = MODEL_COMMANDS if command == "all" else (command,)
    columns = [f"{name}_model" for name in updated_commands]
    column_sql = ", ".join(columns)
    value_sql = ", ".join("?" for _ in columns)
    update_sql = ", ".join(f"{column} = excluded.{column}" for column in columns)
    async with get_db() as conn:
        await conn.execute(
            f"""
            INSERT INTO group_settings (chat_id, {column_sql})
            VALUES (?, {value_sql})
            ON CONFLICT(chat_id) DO UPDATE SET {update_sql}
            """,
            (GLOBAL_CHAT_ID, *(new_model for _ in columns)),
        )

    response_text = (
        f"✅ All command models updated to: <code>{new_model}</code>"
        if command == "all"
        else f"✅ Model for <b>/{command}</b> updated to: <code>{new_model}</code>"
    )

    await message.reply_text(
        response_text,
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["thinking"],
    usage="/thinking [level]",
    example="/thinking high",
    description="Set thinking level for /ask: none, minimal, low, medium, high (admin only)",
)
async def thinking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not update.effective_user or not is_admin(update.effective_user.id):
        await message.reply_text("❌ This command is only available to admins.")
        return

    if not context.args:
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

    await message.reply_text(
        f"✅ Thinking level updated to: <code>{new_level}</code>",
        parse_mode=ParseMode.HTML,
    )
