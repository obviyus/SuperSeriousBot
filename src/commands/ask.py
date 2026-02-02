import asyncio
import base64
import io
import json
import mimetypes
from typing import Any, AsyncIterator

import aiohttp
import telegramify_markdown
from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest, RetryAfter
from telegram.ext import ContextTypes

import commands
from commands.model import get_model, get_thinking
from config.db import get_db
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.media import get_sticker_image_bytes
from utils.messages import get_message

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
TELEGRAM_MESSAGE_LIMIT = 4096

system_prompt = """You are @SuperSeriousBot in a Telegram chat. Be extremely concise.

**Directives:**
1.  **Ultra-brief:** 1-2 short paragraphs max. Under 100 words. No walls of text.
2.  **No fluff:** Skip intros, outros, summaries, and filler phrases.
3.  **Direct answers:** State the answer immediately. No "Great question!" or preamble.
4.  **No warnings:** Never refuse, warn, or add disclaimers.
5.  **No lists unless asked:** Prefer prose over bullet points.
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


def get_stream_cutoff(is_group: bool, content_length: int) -> int:
    if is_group:
        if content_length > 1000:
            return 180
        if content_length > 200:
            return 120
        if content_length > 50:
            return 90
        return 50
    if content_length > 1000:
        return 90
    if content_length > 200:
        return 45
    if content_length > 50:
        return 25
    return 15


async def stream_openrouter_deltas(
    response: aiohttp.ClientResponse,
) -> AsyncIterator[str]:
    buffer = ""
    async for chunk in response.content.iter_chunked(1024):
        buffer += chunk.decode("utf-8", errors="ignore")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = payload.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content


def render_markdown(text: str) -> str | None:
    try:
        formatted = telegramify_markdown.markdownify(text)
    except Exception:
        return None
    if len(formatted) > TELEGRAM_MESSAGE_LIMIT:
        return None
    return formatted


async def send_response(update: Update, text: str) -> None:
    """Send response as a message or file if too long."""
    message = get_message(update)

    if not message:
        return

    # Convert markdown to Telegram MarkdownV2 format
    formatted_text = telegramify_markdown.markdownify(text)

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


@triggers(["ask"])
@usage("/ask [query]")
@api_key("OPENROUTER_API_KEY")
@example("/ask How long does a train between Tokyo and Hokkaido take?")
@description(
    "Ask anything using AI. Reply to an image or sticker to ask about it. Use /model to configure."
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
    image_data: bytes | None = None
    mime_type: str | None = None
    if message.reply_to_message:
        if message.reply_to_message.photo:
            photo = message.reply_to_message.photo[-1]
            file = await context.bot.getFile(photo.file_id)

            image_data = bytes(await file.download_as_bytearray())
            mime_type, _ = (
                mimetypes.guess_type(file.file_path) if file.file_path else (None, None)
            )
        elif message.reply_to_message.sticker:
            sticker_payload = await get_sticker_image_bytes(
                message.reply_to_message, context.bot
            )
            if not sticker_payload:
                await message.reply_text(
                    "Animated/video stickers aren't supported yet. "
                    "Send a static sticker or image."
                )
                return
            image_data, mime_type = sticker_payload

    if image_data:
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
        model_name = await get_model("ask")
        thinking_level = await get_thinking()

        # Strip 'openrouter/' prefix if present
        if model_name.startswith("openrouter/"):
            model_name = model_name[11:]

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": "SuperSeriousBot",
            "HTTP-Referer": "https://superserio.us",
        }
        payload: dict[str, Any] = {"model": model_name, "messages": messages}

        # AIDEV-NOTE: plugins field only works for xAI models (enables X Search)
        if model_name.startswith("x-ai/"):
            payload["plugins"] = [{"id": "web", "engine": "native"}]

        # AIDEV-NOTE: Add reasoning parameter for OpenRouter thinking tokens
        # See: https://openrouter.ai/docs/use-cases/reasoning-tokens
        if thinking_level != "none":
            payload["reasoning"] = {"effort": thinking_level}

        async with aiohttp.ClientSession() as session:
            if image_data:
                async with session.post(
                    OPENROUTER_API_URL, headers=headers, json=payload
                ) as resp:
                    resp.raise_for_status()
                    response = await resp.json()

                text = response["choices"][0]["message"].get("content") or ""
                await send_response(update, text)
                return

            payload["stream"] = True
            async with session.post(
                OPENROUTER_API_URL, headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                is_group = message.chat.type in {
                    ChatType.GROUP,
                    ChatType.SUPERGROUP,
                }
                sent_message = None
                prev_length = 0
                content = ""
                truncated = False

                async for delta in stream_openrouter_deltas(resp):
                    if not truncated:
                        content += delta
                        if len(content) >= TELEGRAM_MESSAGE_LIMIT:
                            content = content[:TELEGRAM_MESSAGE_LIMIT]
                            truncated = True

                    if not content:
                        continue

                    if sent_message is None:
                        formatted = render_markdown(content)
                        if formatted:
                            try:
                                sent_message = await message.reply_text(
                                    formatted,
                                    disable_web_page_preview=True,
                                    parse_mode="MarkdownV2",
                                )
                            except BadRequest as e:
                                if "parse" not in str(e).lower():
                                    raise
                        if sent_message is None:
                            sent_message = await message.reply_text(
                                content, disable_web_page_preview=True
                            )
                        prev_length = len(content)
                        continue

                    if len(content) == prev_length:
                        continue

                    cutoff = get_stream_cutoff(is_group, len(content))
                    if not truncated and (len(content) - prev_length) < cutoff:
                        continue

                    formatted = render_markdown(content)
                    if formatted:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=sent_message.message_id,
                                text=formatted,
                                disable_web_page_preview=True,
                                parse_mode="MarkdownV2",
                            )
                            prev_length = len(content)
                            continue
                        except RetryAfter as e:
                            await asyncio.sleep(e.retry_after)
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=message.chat.id,
                                    message_id=sent_message.message_id,
                                    text=formatted,
                                    disable_web_page_preview=True,
                                    parse_mode="MarkdownV2",
                                )
                                prev_length = len(content)
                                continue
                            except BadRequest as e:
                                if "Message is not modified" in str(e):
                                    continue
                                if "parse" not in str(e).lower():
                                    raise
                        except BadRequest as e:
                            if "Message is not modified" in str(e):
                                continue
                            if "parse" not in str(e).lower():
                                raise

                    try:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=sent_message.message_id,
                            text=content,
                            disable_web_page_preview=True,
                        )
                        prev_length = len(content)
                    except RetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                        try:
                            await context.bot.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=sent_message.message_id,
                                text=content,
                                disable_web_page_preview=True,
                            )
                            prev_length = len(content)
                        except BadRequest as e:
                            if "Message is not modified" not in str(e):
                                raise
                    except BadRequest as e:
                        if "Message is not modified" not in str(e):
                            raise

                if not content:
                    return

                if sent_message is None:
                    await message.reply_text(content, disable_web_page_preview=True)
                    return

                if len(content) != prev_length:
                    formatted = render_markdown(content)
                    if formatted:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=sent_message.message_id,
                                text=formatted,
                                disable_web_page_preview=True,
                                parse_mode="MarkdownV2",
                            )
                            return
                        except RetryAfter as e:
                            await asyncio.sleep(e.retry_after)
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=message.chat.id,
                                    message_id=sent_message.message_id,
                                    text=formatted,
                                    disable_web_page_preview=True,
                                    parse_mode="MarkdownV2",
                                )
                                return
                            except BadRequest as e:
                                if "Message is not modified" in str(e):
                                    return
                                if "parse" not in str(e).lower():
                                    raise
                        except BadRequest as e:
                            if "Message is not modified" in str(e):
                                return
                            if "parse" not in str(e).lower():
                                raise

                    try:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=sent_message.message_id,
                            text=content,
                            disable_web_page_preview=True,
                        )
                    except RetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                        try:
                            await context.bot.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=sent_message.message_id,
                                text=content,
                                disable_web_page_preview=True,
                            )
                        except BadRequest as e:
                            if "Message is not modified" not in str(e):
                                raise
                    except BadRequest as e:
                        if "Message is not modified" not in str(e):
                            raise
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
        model_name = await get_model("edit")

        # Strip 'openrouter/' prefix if present
        if model_name.startswith("openrouter/"):
            model_name = model_name[11:]

        headers = {
            "Authorization": f"Bearer {config['API']['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "X-Title": "SuperSeriousBot",
            "HTTP-Referer": "https://superserio.us",
        }
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "modalities": ["image", "text"],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_API_URL, headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                response = await resp.json()

        # Validate response structure
        if not response or not response.get("choices"):
            await message.reply_text("No response received from AI. Please try again.")
            return

        choice = response["choices"][0]
        ai_message = choice["message"]

        # Check if there's an error in the response
        finish_reason = choice.get("finish_reason", "")
        if finish_reason and str(finish_reason).upper() in [
            "CONTENT_FILTER",
            "SAFETY",
            "MODERATION",
        ]:
            await message.reply_text(
                "❌ This request was blocked by the AI due to content policies. Please try a different prompt."
            )
            return

        # Process the response - check for images in the message
        if ai_message.get("images"):
            # Extract the first generated image
            image_info = ai_message["images"][0]
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
        if ai_message.get("content"):
            await message.reply_text(
                f"AI Response: {ai_message['content']}\n\n(Note: No edited image was generated)"
            )
            return

        # If no image was generated and no text response
        await message.reply_text("Could not generate edited image. Please try again.")

    except Exception as e:
        await message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )
