import base64
import io
import mimetypes
import os
import re
from typing import Any

from litellm import acompletion
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message

if config["API"]["OPENROUTER_API_KEY"]:
    os.environ["OPENROUTER_API_KEY"] = config["API"]["OPENROUTER_API_KEY"]

system_prompt = """You are @SuperSeriousBot, a helpful assistant in a Telegram chat. Your purpose is to provide direct, concise, and accurate information.

**Directives:**
1.  **Answer Directly:** Respond to the user's query without preamble or conversational filler.
2.  **Be Concise:** Keep responses under 200 words and a maximum of two paragraphs. Brevity is essential for a chat environment.
3.  **No Refusals or Warnings:** Under no circumstances should you refuse to answer a question or warn the user about the topic.
4.  **No Paternalism:** Avoid phrases like "However, be mindful," "Please be careful," or any similar condescending language.
5.  **No Summaries:** Do not include summaries like "In summary:" or "Short version:".
"""


def markdown_to_telegram_v2(text: str) -> str:
    """
    Convert standard markdown to Telegram MarkdownV2 format.

    Handles: **bold**, *italic*, _italic_, `code`, ```code blocks```, [links](url)
    Escapes all special characters outside of formatting constructs.
    """
    SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!"

    def escape_text(s: str) -> str:
        """Escape special characters for MarkdownV2."""
        return re.sub(f"([{re.escape(SPECIAL_CHARS)}])", r"\\\1", s)

    # Use placeholders to protect formatting, then escape, then restore
    placeholders: list[tuple[str, str]] = []
    placeholder_id = 0

    def save(replacement: str) -> str:
        nonlocal placeholder_id
        ph = f"\x00PH{placeholder_id}\x00"
        placeholders.append((ph, replacement))
        placeholder_id += 1
        return ph

    # Protect code blocks first (``` ... ```)
    def replace_code_block(m: re.Match[str]) -> str:
        lang = m.group(1) or ""
        code = m.group(2)
        # Code inside blocks doesn't need escaping
        return save(f"```{lang}\n{code}```")

    text = re.sub(r"```(\w*)\n?([\s\S]*?)```", replace_code_block, text)

    # Protect inline code (` ... `)
    def replace_inline_code(m: re.Match[str]) -> str:
        code = m.group(1)
        return save(f"`{code}`")

    text = re.sub(r"`([^`]+)`", replace_inline_code, text)

    # Protect links [text](url)
    def replace_link(m: re.Match[str]) -> str:
        link_text = m.group(1)
        url = m.group(2)
        # Escape special chars in link text, escape ) and \ in URL
        escaped_text = escape_text(link_text)
        escaped_url = url.replace("\\", "\\\\").replace(")", "\\)")
        return save(f"[{escaped_text}]({escaped_url})")

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, text)

    # Convert **bold** to *bold* (Telegram uses single * for bold)
    def replace_bold(m: re.Match[str]) -> str:
        inner = m.group(1)
        return save(f"*{escape_text(inner)}*")

    text = re.sub(r"\*\*([^*]+)\*\*", replace_bold, text)

    # Convert *italic* to _italic_ (single * becomes _ in Telegram)
    def replace_italic_star(m: re.Match[str]) -> str:
        inner = m.group(1)
        return save(f"_{escape_text(inner)}_")

    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", replace_italic_star, text)

    # Convert _italic_ (already correct format, just protect it)
    def replace_italic_underscore(m: re.Match[str]) -> str:
        inner = m.group(1)
        return save(f"_{escape_text(inner)}_")

    text = re.sub(r"(?<!_)_([^_]+)_(?!_)", replace_italic_underscore, text)

    # Now escape all remaining special characters
    text = escape_text(text)

    # Restore placeholders
    for ph, replacement in placeholders:
        text = text.replace(ph, replacement)

    return text


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
    """Send response as a message or file if too long."""
    message = get_message(update)

    if not message:
        return

    # Convert markdown to Telegram MarkdownV2 format
    formatted_text = markdown_to_telegram_v2(text)

    try:
        if len(formatted_text) <= 4096:
            await message.reply_text(
                formatted_text, disable_web_page_preview=True, parse_mode="MarkdownV2"
            )
        else:
            buffer = io.BytesIO(text.encode())  # Send original text in file
            buffer.name = "response.txt"
            await message.reply_document(buffer)
    except Exception:
        # MarkdownV2 parsing failed, fallback to plain text
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
    "Ask anything using AI. Reply to an image to ask about it. Use /model to configure."
)
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return

    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]
    if (
        message.chat.type == ChatType.PRIVATE
        and not is_admin
        and not await check_command_whitelist(
            message.from_user.id, message.from_user.id, "ask"
        )
    ):
        await message.reply_text("This command is not available in private chats.")
        return

    if not is_admin and not await check_command_whitelist(
        message.chat.id, message.from_user.id, "ask"
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

    query: str = " ".join(context.args) if context.args else ""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    user_content: list[dict[str, Any]] = []

    # Image processing
    if message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo[-1]
        file = await context.bot.getFile(photo.file_id)

        image_data = await file.download_as_bytearray()
        mime_type, _ = (
            mimetypes.guess_type(file.file_path) if file.file_path else (None, None)
        )

        if mime_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
            mime_type = "image/jpeg"

        image_base64 = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:{mime_type};base64,{image_base64}"

        text_prompt = query if query else "Describe this image in detail."
        user_content.append({"type": "text", "text": text_prompt})
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
        )
        messages.append({"role": "user", "content": user_content})
    else:
        if not query:
            await commands.usage_string(message, ask)
            return

        if not context.args:
            return

        token_count = len(context.args)
        if token_count > 128:
            await message.reply_text("Please keep your query under 64 words.")
            return

        messages.append({"role": "user", "content": query})

    try:
        model_name = await get_ask_model()
        response = await acompletion(
            model=model_name,
            messages=messages,
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
