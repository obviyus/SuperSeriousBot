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

if config["API"]["OPENROUTER_API_KEY"]:
    os.environ["OPENROUTER_API_KEY"] = config["API"]["OPENROUTER_API_KEY"]

if config["API"]["GOOGLE_API_KEY"]:
    os.environ["GEMINI_API_KEY"] = config["API"]["GOOGLE_API_KEY"]

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
    """Send response as a message or file if too long."""
    try:
        if len(text) <= 4096:
            await update.message.reply_text(
                text, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN
            )
        else:
            buffer = io.BytesIO(text.encode())
            buffer.name = "response.txt"
            await update.message.reply_document(buffer)
    except Exception:
        # Markdown parsing failed, fallback to plain text
        if len(text) <= 4096:
            await update.message.reply_text(text, disable_web_page_preview=True)
        else:
            buffer = io.BytesIO(text.encode())
            buffer.name = "response.txt"
            await update.message.reply_document(buffer)


async def get_ai_model() -> str:
    """Get the configured AI model from database, fallback to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT ai_model FROM group_settings WHERE chat_id = ?",
            (-1,),  # AIDEV-NOTE: Global settings use chat_id = -1
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "openrouter/google/gemini-2.5-flash"


@triggers(["ask"])
@usage("/ask [-m] [query]")
@api_key("GOOGLE_API_KEY")
@example("/ask How long does a train between Tokyo and Hokkaido take?")
@description(
    "Ask anything using AI with Google search grounding. Use -m for custom model."
)
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.message.chat.type == ChatType.PRIVATE
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
        and not await check_command_whitelist(
            update.message.from_user.id, update.message.from_user.id, "ask"
        )
    ):
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    if not context.args:
        await commands.usage_string(update.message, ask)
        return

    if (
        not await check_command_whitelist(
            update.message.chat.id, update.message.from_user.id, "ask"
        )
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
    ):
        await update.message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    # Check for -m parameter
    use_custom_model = False
    args = list(context.args)

    if args and args[0] == "-m":
        use_custom_model = True
        args.pop(0)  # Remove -m from args

        # Check if custom model requires OpenRouter API key
        if not config["API"]["OPENROUTER_API_KEY"]:
            await update.message.reply_text(
                "Custom model option requires OPENROUTER_API_KEY to be configured."
            )
            return

    query: str = " ".join(args)
    token_count = len(args)

    if token_count > 64:
        await update.message.reply_text("Please keep your query under 64 words.")
        return

    try:
        if use_custom_model:
            # Use custom model from database with OpenRouter
            model_name = await get_ai_model()
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
                api_key=config["API"]["OPENROUTER_API_KEY"],
            )
        else:
            # Use Google AI Studio with search grounding
            tools = [{"googleSearch": {}}]  # Enable Google Search grounding
            response = await acompletion(
                model="gemini/gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                tools=tools,
                max_tokens=1000,
                api_key=config["API"]["GOOGLE_API_KEY"],
            )

        text = response.choices[0].message.content
        await send_response(update, text)
    except Exception as e:
        await update.message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )


@triggers(["caption"])
@usage("/caption")
@api_key("OPENROUTER_API_KEY")
@example("/caption")
@description("Reply to an image to caption it using vision models.")
async def caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]
    if not is_admin and update.message.chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await commands.usage_string(update.message, caption)
        return

    if not is_admin and not await check_command_whitelist(
        update.message.chat.id, update.message.from_user.id, "caption"
    ):
        await update.message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    photo = update.message.reply_to_message.photo[-1]
    file = await context.bot.getFile(photo.file_id)

    # Download the image and convert it to a data URL that includes a supported MIME type.
    image_data = await file.download_as_bytearray()
    mime_type, _ = mimetypes.guess_type(file.file_path)
    if mime_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        mime_type = "image/jpeg"
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    image_url = f"data:{mime_type};base64,{image_base64}"

    custom_prompt = " ".join(context.args) or ""

    try:
        response = await acompletion(
            model="openrouter/x-ai/grok-4-fast:free",
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

        text = response.choices[0].message.content
        try:
            await update.message.reply_text(
                text, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            # Markdown parsing failed, fallback to plain text
            await update.message.reply_text(text, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(
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
    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]

    # Check if in private chat and not admin
    if not is_admin and update.message.chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    # Check if replying to a message with a photo
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await commands.usage_string(update.message, edit)
        return

    # Check command whitelist
    if not is_admin and not await check_command_whitelist(
        update.message.chat.id, update.message.from_user.id, "edit"
    ):
        await update.message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    # Get the prompt from args
    if not context.args:
        await update.message.reply_text(
            "Please provide a prompt describing how to edit the image."
        )
        return

    prompt = " ".join(context.args)

    try:
        # Get the photo file
        photo = update.message.reply_to_message.photo[-1]
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

        # Call OpenRouter API for image generation/editing
        response = await acompletion(
            model="openrouter/google/gemini-2.5-flash-image-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            modalities=["image", "text"],
            extra_headers={
                "X-Title": "SuperSeriousBot",
                "HTTP-Referer": "https://superserio.us",
            },
            api_key=config["API"]["OPENROUTER_API_KEY"],
        )

        # Validate response structure
        if not response or not response.choices:
            await update.message.reply_text(
                "No response received from AI. Please try again."
            )
            return

        choice = response.choices[0]
        message = choice.message

        # Check if there's an error in the response
        if hasattr(choice, "finish_reason") and choice.finish_reason:
            if str(choice.finish_reason).upper() in [
                "CONTENT_FILTER",
                "SAFETY",
                "MODERATION",
            ]:
                await update.message.reply_text(
                    "❌ This request was blocked by the AI due to content policies. Please try a different prompt."
                )
                return

        # Process the response - check for images in the message
        if hasattr(message, "images") and message.images:
            # Extract the first generated image
            image_info = message.images[0]
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

                    await update.message.reply_photo(buffer, caption=caption)
                    return

        # If no image was generated, check for text response
        if message.content:
            await update.message.reply_text(
                f"AI Response: {message.content}\n\n(Note: No edited image was generated)"
            )
            return

        # If no image was generated and no text response
        await update.message.reply_text(
            "Could not generate edited image. Please try again."
        )

    except Exception as e:
        await update.message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )
