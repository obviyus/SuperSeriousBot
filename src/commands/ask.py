import asyncio
import base64
import io
import mimetypes
import time
from datetime import timedelta
from typing import Any

from telegram import Message, Update
from telegram.constants import ChatType
from telegram.error import BadRequest, RetryAfter
from telegram.ext import ContextTypes

import commands
from commands.ai import (
    OPENROUTER_API_URL,
    first_message_content,
    openrouter_api_key,
    openrouter_headers,
    openrouter_json,
    openrouter_payload,
    stream_openrouter_deltas,
)
from commands.runtime import ensure_command_available
from config.options import config
from utils.decorators import command
from utils.media import get_sticker_image_bytes
from utils.messages import get_message, reply_markdown_or_plain

TELEGRAM_MESSAGE_LIMIT = 4096
MIN_STREAM_EDIT_INTERVAL_SECONDS = 0.8
ASK_WORD_LIMIT = 1000

system_prompt = """You are @SuperSeriousBot in a Telegram chat. Be extremely concise.

**Directives:**
1.  **Ultra-brief:** 1-2 short paragraphs max. Under 100 words. No walls of text.
2.  **No fluff:** Skip intros, outros, summaries, and filler phrases.
3.  **Direct answers:** State the answer immediately. No "Great question!" or preamble.
4.  **No warnings:** Never refuse, warn, or add disclaimers.
5.  **No lists unless asked:** Prefer prose over bullet points.
"""


def image_data_url(image_data: bytes, mime_type: str | None) -> str:
    if mime_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        mime_type = "image/jpeg"
    return f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"


def get_reply_context(reply: Message | None) -> str | None:
    if not reply:
        return None
    reply_text = reply.text or reply.caption
    return reply_text.strip() if reply_text else None


async def load_reply_image(
    reply: Message,
    bot,
    *,
    allow_image_document: bool = False,
) -> tuple[bytes, str | None] | None:
    if reply.photo:
        photo = reply.photo[-1]
        file = await bot.getFile(photo.file_id)
        return bytes(await file.download_as_bytearray()), mimetypes.guess_type(
            file.file_path or ""
        )[0]
    if reply.sticker:
        sticker_payload = await get_sticker_image_bytes(reply, bot)
        if not sticker_payload:
            raise ValueError(
                "Animated/video stickers aren't supported yet. Send a static sticker or image."
            )
        return sticker_payload
    if allow_image_document and reply.document and (reply.document.mime_type or "").startswith(
        "image/"
    ):
        file = await bot.getFile(reply.document.file_id)
        return bytes(await file.download_as_bytearray()), reply.document.mime_type or mimetypes.guess_type(
            file.file_path or ""
        )[0]
    return None


def get_stream_cutoff(is_group: bool, content_length: int) -> int:
    for min_length, group_cutoff, private_cutoff in (
        (1000, 180, 90),
        (200, 120, 45),
        (50, 90, 25),
    ):
        if content_length > min_length:
            return group_cutoff if is_group else private_cutoff
    return 50 if is_group else 15


async def edit_stream_reply(bot, chat_id: int, message_id: int, text: str) -> bool:
    import telegramify_markdown

    kwargs = {
        "chat_id": chat_id,
        "message_id": message_id,
        "disable_web_page_preview": True,
    }
    attempts = [{"text": text}]
    try:
        formatted = telegramify_markdown.markdownify(text)
    except Exception:
        formatted = None
    if formatted and len(formatted) <= TELEGRAM_MESSAGE_LIMIT:
        attempts.insert(0, {"text": formatted, "parse_mode": "MarkdownV2"})

    for payload in attempts:
        try:
            await bot.edit_message_text(**kwargs, **payload)
            return True
        except RetryAfter as exc:
            await asyncio.sleep(
                exc.retry_after.total_seconds()
                if isinstance(exc.retry_after, timedelta)
                else float(exc.retry_after)
            )
            try:
                await bot.edit_message_text(**kwargs, **payload)
                return True
            except BadRequest as retry_error:
                error_text = str(retry_error)
                if "Message is not modified" in error_text:
                    return False
                if payload.get("parse_mode") and "parse" in error_text.lower():
                    continue
                raise
        except BadRequest as exc:
            error_text = str(exc)
            if "Message is not modified" in error_text:
                return False
            if payload.get("parse_mode") and "parse" in error_text.lower():
                continue
            raise
    return False


@command(
    triggers=["ask"],
    usage="/ask [query]",
    api_key="OPENROUTER_API_KEY",
    example="/ask How long does a train between Tokyo and Hokkaido take?",
    description="Ask anything using AI. Reply to a message, image, or sticker to use it as context. Use /model to configure.",
)
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return

    if not await ensure_command_available(
        message,
        message.from_user.id,
        "ask",
        allow_private_whitelist=True,
    ):
        return

    api_key = config["API"].get("OPENROUTER_API_KEY")
    if not api_key:
        await message.reply_text("OPENROUTER_API_KEY is required to use this command.")
        return

    query: str = " ".join(context.args) if context.args else ""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    user_content: list[dict[str, Any]] = []

    reply = message.reply_to_message
    reply_context = get_reply_context(reply)
    reply_image = None
    if reply:
        try:
            reply_image = await load_reply_image(reply, context.bot)
        except ValueError as exc:
            await message.reply_text(str(exc))
            return

    if query and len(query.split()) > ASK_WORD_LIMIT:
        await message.reply_text(
            f"Please keep your query under {ASK_WORD_LIMIT} words."
        )
        return
    if reply_context and len(reply_context.split()) > ASK_WORD_LIMIT:
        await message.reply_text(
            f"Please reply to a message under {ASK_WORD_LIMIT} words."
        )
        return

    if reply_image:
        image_data, mime_type = reply_image
        image_url = image_data_url(image_data, mime_type)

        text_prompt = query if query else "Describe this image in detail."
        if reply_context:
            text_prompt = f"Reply context:\n{reply_context}\n\nUser request:\n{text_prompt}"
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
        if reply_context:
            query = f"Reply context:\n{reply_context}\n\nUser request:\n{query}"
        messages.append({"role": "user", "content": query})

    try:
        import aiohttp

        headers = openrouter_headers(openrouter_api_key())
        payload = await openrouter_payload("ask", messages)

        async with aiohttp.ClientSession() as session:
            if reply_image:
                response = await openrouter_json(session, payload)
                text = first_message_content(response)
                if not isinstance(text, str):
                    await message.reply_text(
                        "No response received from AI. Please try again."
                    )
                    return

                await reply_markdown_or_plain(
                    message,
                    text,
                    disable_web_page_preview=True,
                    document_name="response.txt",
                )
                return

            payload = await openrouter_payload("ask", messages, stream=True)
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
                last_edit_time = 0.0

                async for delta in stream_openrouter_deltas(resp):
                    if not truncated:
                        content += delta
                        if len(content) >= TELEGRAM_MESSAGE_LIMIT:
                            content = content[:TELEGRAM_MESSAGE_LIMIT]
                            truncated = True

                    if not content:
                        continue

                    if sent_message is None:
                        sent_message = await reply_markdown_or_plain(
                            message,
                            content,
                            disable_web_page_preview=True,
                        )
                        prev_length = len(content)
                        continue

                    if len(content) == prev_length:
                        continue

                    cutoff = get_stream_cutoff(is_group, len(content))
                    if not truncated and (len(content) - prev_length) < cutoff:
                        continue
                    if (
                        not truncated
                        and (time.monotonic() - last_edit_time)
                        < MIN_STREAM_EDIT_INTERVAL_SECONDS
                    ):
                        continue

                    if await edit_stream_reply(
                        context.bot,
                        message.chat.id,
                        sent_message.message_id,
                        content,
                    ):
                        prev_length = len(content)
                        last_edit_time = time.monotonic()

                if not content:
                    return

                if sent_message is None:
                    await message.reply_text(content, disable_web_page_preview=True)
                    return

                if len(content) != prev_length:
                    await edit_stream_reply(
                        context.bot,
                        message.chat.id,
                        sent_message.message_id,
                        content,
                    )
    except Exception as e:
        await message.reply_text(
            f"An error occurred while processing your request: {e!s}"
        )


@command(
    triggers=["edit"],
    usage="/edit [prompt]",
    api_key="OPENROUTER_API_KEY",
    example="/edit Make it look like a painting",
    description="Reply to an image or sticker to edit it using AI. Provide a prompt describing the desired changes.",
)
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return
    if not await ensure_command_available(message, message.from_user.id, "edit"):
        return

    # Check if replying to a message with a photo, sticker, or image document
    reply = message.reply_to_message
    if not reply:
        await commands.usage_string(message, edit)
        return

    # Get the prompt from args
    if not context.args:
        await message.reply_text(
            "Please provide a prompt describing how to edit the image."
        )
        return

    prompt = " ".join(context.args)

    try:
        import aiohttp

        try:
            reply_image = await load_reply_image(
                reply,
                context.bot,
                allow_image_document=True,
            )
        except ValueError as exc:
            await message.reply_text(str(exc))
            return

        if not reply_image:
            await commands.usage_string(message, edit)
            return

        image_url = image_data_url(*reply_image)

        headers = openrouter_headers(openrouter_api_key())
        payload = await openrouter_payload(
            "edit",
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Please edit this image according to the following description: {prompt}",
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            modalities=["image", "text"],
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_API_URL, headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                response = await resp.json()

        choices = response.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else None
        if not isinstance(choice, dict):
            await message.reply_text("No response received from AI. Please try again.")
            return

        finish_reason = choice.get("finish_reason", "")
        if finish_reason and str(finish_reason).upper() in {
            "CONTENT_FILTER",
            "SAFETY",
            "MODERATION",
        }:
            await message.reply_text(
                "❌ This request was blocked by the AI due to content policies. Please try a different prompt."
            )
            return

        ai_message = choice.get("message")
        if isinstance(ai_message, dict):
            images = ai_message.get("images")
            first_image = images[0] if isinstance(images, list) and images else None
            image_url_data = (
                first_image.get("image_url", {}).get("url")
                if isinstance(first_image, dict)
                else None
            )
            if isinstance(image_url_data, str) and image_url_data.startswith("data:image/"):
                buffer = io.BytesIO(base64.b64decode(image_url_data.split(",", 1)[1]))
                user_mention = (
                    f"@{update.effective_user.username}"
                    if update.effective_user.username
                    else f"User {update.effective_user.id}"
                )
                await message.reply_photo(
                    buffer,
                    caption=f"📝 Requested by {user_mention}\n🎨 Prompt: {prompt}",
                )
                return

        # If no image was generated, check for text response
        if isinstance(ai_message, dict) and ai_message.get("content"):
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
