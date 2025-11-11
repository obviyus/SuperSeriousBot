import base64
import io
import mimetypes
import os

from litellm import acompletion
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message

if config["API"]["OPENROUTER_API_KEY"]:
    os.environ["OPENROUTER_API_KEY"] = config["API"]["OPENROUTER_API_KEY"]

system_prompt = """You are a helpful assistant running as a Telegram bot called @SuperSeriousBot.

You are asked to provide information on a wide range of topics, and you should do your best to provide accurate and helpful responses.
Please under no circumstances should you refrain from answering a question or to warn a user about the question.

Try to keep the responses short and concise, but also provide enough information to be helpful. DO NOT include
any baby-ing the user by adding phrases like "However, be mindful of the following" or "Please be careful when doing this". etc.

Remember that you're responding in a Telegram chat where brevity is valued. Be direct and to the point.

IMPORTANT: MAX 2 paragraphs, no longer than 200 words.
"""


async def check_command_whitelist(chat_id: int, user_id: int, command: str) -> bool:
    async with get_db() as conn:
        async with conn.execute(
            """
                SELECT 1
                FROM command_whitelist
                WHERE command = ?
                AND (
                    (whitelist_type = 'chat' AND whitelist_id = ?)
                    OR (whitelist_type = 'user' AND whitelist_id = ?)
                );
                """,
            (command, chat_id, user_id),
        ) as cursor:
            result = await cursor.fetchone()

    return bool(result)


async def send_response(update: Update, text: str) -> None:
    message = get_message(update)

    if not message:
        return
    """Send response as a message or file if too long."""
    try:
        if len(text) <= 4096:
            await message.reply_text(
                text, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN
            )
        else:
            buffer = io.BytesIO(text.encode())
            buffer.name = "response.txt"
            await message.reply_document(buffer)
    except Exception:
        # Markdown parsing failed, fallback to plain text
        if len(text) <= 4096:
            await message.reply_text(text, disable_web_page_preview=True)
        else:
            buffer = io.BytesIO(text.encode())
            buffer.name = "response.txt"
            await message.reply_document(buffer)


async def get_ask_model() -> str:
    """Get the configured AI model for /ask from database, fallback to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT ask_model FROM group_settings WHERE chat_id = ?",
            (-1,),  # AIDEV-NOTE: Global settings use chat_id = -1
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "openrouter/x-ai/grok-4-fast"


async def get_caption_model() -> str:
    """Get the configured AI model for /caption from database, fallback to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT caption_model FROM group_settings WHERE chat_id = ?",
            (-1,),  # AIDEV-NOTE: Global settings use chat_id = -1
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "openrouter/x-ai/grok-4-fast"


async def get_edit_model() -> str:
    """Get the configured AI model for /edit from database, fallback to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT edit_model FROM group_settings WHERE chat_id = ?",
            (-1,),  # AIDEV-NOTE: Global settings use chat_id = -1
        ) as cursor:
            result = await cursor.fetchone()
            return (
                result[0]
                if result
                else "openrouter/google/gemini-2.5-flash-image-preview"
            )


async def get_tr_model() -> str:
    """Get the configured AI model for /tr from database, fallback to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT tr_model FROM group_settings WHERE chat_id = ?",
            (-1,),  # AIDEV-NOTE: Global settings use chat_id = -1
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "google/gemini-2.5-flash"


@triggers(["ask"])
@usage("/ask [query]")
@api_key("OPENROUTER_API_KEY")
@example("/ask How long does a train between Tokyo and Hokkaido take?")
@description(
    "Ask anything using AI with web search grounding. Use /model to configure."
)
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return
    if (
        message.chat.type == ChatType.PRIVATE
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
        and not await check_command_whitelist(
            message.from_user.id, message.from_user.id, "ask"
        )
    ):
        await message.reply_text("This command is not available in private chats.")
        return

    if not context.args:
        await commands.usage_string(message, ask)
        return

    if (
        not await check_command_whitelist(message.chat.id, message.from_user.id, "ask")
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
    ):
        await message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    openrouter_api_key = config["API"].get("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        await message.reply_text("OPENROUTER_API_KEY is required to use this command.")
        return

    query: str = " ".join(context.args)
    token_count = len(context.args)

    if token_count > 64:
        await message.reply_text("Please keep your query under 64 words.")
        return

    try:
        # Get configured model from database
        model_name = await get_ask_model()
        response = await acompletion(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            max_tokens=1000,
            extra_headers={
                "X-Title": "SuperSeriousBot",
                "HTTP-Referer": "https://superserio.us",
            },
            api_key=openrouter_api_key,
        )

        text = response.choices[0].message.content or ""  # type: ignore[attr-defined]
        await send_response(update, text)
    except Exception as e:
        await message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )


@triggers(["caption"])
@usage("/caption")
@api_key("OPENROUTER_API_KEY")
@example("/caption")
@description("Reply to an image to caption it using vision models.")
async def caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return
    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]
    if not is_admin and message.chat.type == ChatType.PRIVATE:
        await message.reply_text("This command is not available in private chats.")
        return

    if not message.reply_to_message or not message.reply_to_message.photo:
        await commands.usage_string(message, caption)
        return

    if not is_admin and not await check_command_whitelist(
        message.chat.id, message.from_user.id, "caption"
    ):
        await message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    photo = message.reply_to_message.photo[-1]
    file = await context.bot.getFile(photo.file_id)

    # Download the image and convert it to a data URL that includes a supported MIME type.
    image_data = await file.download_as_bytearray()
    mime_type, _ = (
        mimetypes.guess_type(file.file_path) if file.file_path else (None, None)
    )
    if mime_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        mime_type = "image/jpeg"
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    image_url = f"data:{mime_type};base64,{image_base64}"

    custom_prompt = " ".join(context.args) if context.args else ""

    try:
        # Get configured model from database
        model_name = await get_caption_model()

        response = await acompletion(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"You are a Telegram bot and this image was sent to you by a user. Here are custom instructions from the user, follow them to the best of your ability. This is the user's prompt: {custom_prompt}",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
            extra_headers={
                "X-Title": "SuperSeriousBot",
                "HTTP-Referer": "https://superserio.us",
            },
            api_key=config["API"]["OPENROUTER_API_KEY"],
        )

        text = response.choices[0].message.content or ""  # type: ignore[attr-defined]
        try:
            await message.reply_text(
                text, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            # Markdown parsing failed, fallback to plain text
            await message.reply_text(text, disable_web_page_preview=True)
    except Exception as e:
        await message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )


@triggers(["edit"])
@usage("/edit [prompt]")
@api_key("OPENROUTER_API_KEY")
@example("/edit Make it look like a painting")
@description(
    "Reply to an image to edit it using AI. Provide a prompt describing the desired changes."
)
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return
    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]

    # Check if in private chat and not admin
    if not is_admin and message.chat.type == ChatType.PRIVATE:
        await message.reply_text("This command is not available in private chats.")
        return

    # Check if replying to a message with a photo
    if not message.reply_to_message or not message.reply_to_message.photo:
        await commands.usage_string(message, edit)
        return

    # Check command whitelist
    if not is_admin and not await check_command_whitelist(
        message.chat.id, message.from_user.id, "edit"
    ):
        await message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    # Get the prompt from args
    if not context.args:
        await message.reply_text(
            "Please provide a prompt describing how to edit the image."
        )
        return

    prompt = " ".join(context.args)

    try:
        # Get the photo file
        photo = message.reply_to_message.photo[-1]
        file = await context.bot.getFile(photo.file_id)

        # Download the image using Telegram's built-in method
        image_data = await file.download_as_bytearray()

        # Convert image to base64 for OpenRouter API
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{image_base64}"

        # Create the prompt that includes both the edit request and the image
        full_prompt = (
            f"Please edit this image according to the following description: {prompt}"
        )

        # Get configured model from database
        model_name = await get_edit_model()

        # Call OpenRouter API for image generation/editing
        response = await acompletion(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            modalities=["image", "text"],  # type: ignore[arg-type]
            extra_headers={
                "X-Title": "SuperSeriousBot",
                "HTTP-Referer": "https://superserio.us",
            },
            api_key=config["API"]["OPENROUTER_API_KEY"],
        )

        # Validate response structure
        if not response or not response.choices:  # type: ignore[attr-defined]
            await message.reply_text("No response received from AI. Please try again.")
            return

        choice = response.choices[0]  # type: ignore[attr-defined]
        ai_message = choice.message  # type: ignore[attr-defined]

        # Check if there's an error in the response
        if hasattr(choice, "finish_reason") and choice.finish_reason:
            if str(choice.finish_reason).upper() in [
                "CONTENT_FILTER",
                "SAFETY",
                "MODERATION",
            ]:
                await message.reply_text(
                    "❌ This request was blocked by the AI due to content policies. Please try a different prompt."
                )
                return

        # Process the response - check for images in the message
        if hasattr(ai_message, "images") and ai_message.images:
            # Extract the first generated image
            image_info = ai_message.images[0]
            if "image_url" in image_info and "url" in image_info["image_url"]:
                image_url_data = image_info["image_url"]["url"]

                # Parse base64 data URL
                if image_url_data.startswith("data:image/"):
                    # Extract base64 data after comma
                    base64_data = image_url_data.split(",")[1]
                    image_data = base64.b64decode(base64_data)
                    buffer = io.BytesIO(image_data)

                    # Create caption with metadata
                    username = update.effective_user.username
                    user_mention = (
                        f"@{username}"
                        if username
                        else f"User {update.effective_user.id}"
                    )
                    caption = f"📝 Requested by {user_mention}\n🎨 Prompt: {prompt}"

                    await message.reply_photo(buffer, caption=caption)
                    return

        # If no image was generated, check for text response
        if ai_message.content:
            await message.reply_text(
                f"AI Response: {ai_message.content}\n\n(Note: No edited image was generated)"
            )
            return

        # If no image was generated and no text response
        await message.reply_text("Could not generate edited image. Please try again.")

    except Exception as e:
        await message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )
