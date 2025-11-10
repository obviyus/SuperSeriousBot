from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from config.options import config
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message

# AIDEV-NOTE: Global AI model setting uses chat_id = -1 in group_settings table
GLOBAL_CHAT_ID = -1


@triggers(["model"])
@usage("/model [model_name]")
@example("/model openrouter/google/gemini-2.0-flash-thinking-exp-1219:free")
@description("Set the AI model for /ask and /caption commands (admin only)")
async def model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not update.effective_user:
        return
    # Check if user is admin
    if str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]:
        await message.reply_text("❌ This command is only available to admins.")
        return
    if not context.args:
        # Show current model
        async with get_db() as conn:
            async with conn.execute(
                "SELECT ai_model FROM group_settings WHERE chat_id = ?",
                (GLOBAL_CHAT_ID,),
            ) as cursor:
                result = await cursor.fetchone()
                current_model = (
                    result[0] if result else "openrouter/google/gemini-2.5-flash"
                )

        text = f"Current AI model: <code>{current_model}</code>\n\n"
        text += "To change, use: <code>/model &lt;model_name&gt;</code>\n"
        text += "Example: <code>/model openrouter/google/gemini-3.0-flash</code>"

        await message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )
        return

    new_model = " ".join(context.args)

    async with get_db() as conn:
        # Insert or update the global model setting
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, ai_model)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET ai_model = excluded.ai_model
            """,
            (GLOBAL_CHAT_ID, new_model),
        )
        await conn.commit()

    await message.reply_text(
        f"AI model updated to: `{new_model}`",
        parse_mode="Markdown",
    )
