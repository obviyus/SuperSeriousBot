import asyncio
import base64
import io
import time
from datetime import timedelta

import ai
import httpx2
from telegram import Message, Update
from telegram.constants import ChatType
from telegram.error import BadRequest, RetryAfter, TelegramError
from telegram.ext import ContextTypes

import commands
from commands.ai import OPENROUTER_BASE_URL, OPENROUTER_HEADERS, model, stream_model
from commands.runtime import HandledCommandError, ensure_command_available
from config.logger import logger
from config.options import config
from utils.command_limits import ensure_quota
from utils.decorators import command
from utils.media import get_message_image_bytes
from utils.messages import get_message, reply_markdown_or_plain

TELEGRAM_MESSAGE_LIMIT = 4096
MIN_STREAM_EDIT_INTERVAL_SECONDS = 0.8
ASK_WORD_LIMIT = 1000
IMAGE_REQUEST_TIMEOUT_SECONDS = 360

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


class OpenRouterImageError(RuntimeError):
    def __init__(self, status: int, detail: str | None) -> None:
        diagnostic = f"OpenRouter image rejected status={status}"
        if detail:
            diagnostic += f" detail={detail}"
        super().__init__(diagnostic)
        self.user_message = (
            "The generated image was rejected by content moderation. "
            "Try a different prompt or source image."
            if detail == "Generated image rejected by content moderation."
            else "AI request failed. Please try again."
        )


def build_image_request(
    model_id: str,
    prompt: str,
    source_image: tuple[bytes, str | None] | None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "model": model_id,
        "prompt": (
            f"Please edit this image according to the following description: {prompt}"
            if source_image
            else f"Please generate an image according to the following description: {prompt}"
        ),
    }
    if source_image:
        request["input_references"] = [
            {
                "type": "image_url",
                "image_url": {"url": image_data_url(*source_image)},
            }
        ]
    return request


async def image_rejection(response: httpx2.Response) -> OpenRouterImageError:
    try:
        data = response.json()
    except ValueError:
        data = None
    error = data.get("error") if isinstance(data, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    detail = " ".join(message.split()) if isinstance(message, str) else None
    if detail and (len(detail) > 300 or "base64" in detail.lower()):
        detail = None
    return OpenRouterImageError(response.status_code, detail)


async def generate_image(request: dict[str, object]) -> bytes:
    headers = {
        "Authorization": f"Bearer {config.API.OPENROUTER_API_KEY}",
        **OPENROUTER_HEADERS,
    }
    timeout = httpx2.Timeout(IMAGE_REQUEST_TIMEOUT_SECONDS)
    async with httpx2.AsyncClient(
        headers=headers, timeout=timeout, follow_redirects=True
    ) as session:
        response = await session.post(f"{OPENROUTER_BASE_URL}/images", json=request)
        if response.status_code >= 400:
            raise await image_rejection(response)
        response.raise_for_status()
        data = response.json()

    images = data.get("data") if isinstance(data, dict) else None
    first_image = images[0] if isinstance(images, list) and images else None
    encoded_image = (
        first_image.get("b64_json") if isinstance(first_image, dict) else None
    )
    if not isinstance(encoded_image, str):
        raise TypeError("OpenRouter did not return image data.")
    return base64.b64decode(encoded_image, validate=True)


def get_reply_context(reply: Message | None) -> str | None:
    if not reply:
        return None
    reply_text = reply.text or reply.caption
    return reply_text.strip() if reply_text else None


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
    except (TypeError, ValueError):
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
    if not await ensure_quota(message, message.from_user.id, "ask"):
        return

    api_key = config.API.OPENROUTER_API_KEY
    if not api_key:
        await message.reply_text("AI is not configured for this command.")
        return

    query: str = " ".join(context.args) if context.args else ""
    messages = [ai.system_message(system_prompt)]

    reply = message.reply_to_message
    reply_context = get_reply_context(reply)
    reply_image = None
    if reply:
        try:
            reply_image = await get_message_image_bytes(reply, context.bot)
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
        text_prompt = query if query else "Describe this image in detail."
        if reply_context:
            text_prompt = (
                f"Reply context:\n{reply_context}\n\nUser request:\n{text_prompt}"
            )
        messages.append(
            ai.user_message(
                text_prompt,
                ai.file_part(image_data, media_type=mime_type or "image/jpeg"),
            )
        )
    else:
        if not query:
            await commands.usage_string(message, ask)
            return
        if reply_context:
            query = f"Reply context:\n{reply_context}\n\nUser request:\n{query}"
        messages.append(ai.user_message(query))

    try:
        is_group = message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}
        sent_message = None
        prev_length = 0
        content = ""
        truncated = False
        last_edit_time = 0.0

        async with stream_model("ask", messages) as stream:
            async for event in stream:
                if not isinstance(event, ai.events.TextDelta):
                    continue
                if not truncated:
                    content += event.chunk
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
            await message.reply_text("No response received from AI. Please try again.")
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
    except (ai.AIError, TelegramError, TimeoutError, TypeError, ValueError):
        logger.exception("Ask command failed")
        await message.reply_text("AI request failed. Please try again.")


@command(
    triggers=["edit"],
    usage="/edit [prompt]",
    api_key="OPENROUTER_API_KEY",
    example="/edit Make it look like a painting",
    description="Generate an image from a prompt. Reply to an image or sticker to edit it instead.",
)
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user or not update.effective_user:
        return
    if not await ensure_command_available(message, message.from_user.id, "edit"):
        return
    if not await ensure_quota(message, message.from_user.id, "edit"):
        return

    if not context.args:
        await message.reply_text("Please provide a prompt describing the image.")
        return

    prompt = " ".join(context.args)
    reply = message.reply_to_message

    try:
        reply_image = None
        if reply:
            try:
                reply_image = await get_message_image_bytes(
                    reply,
                    context.bot,
                    allow_document=True,
                )
            except ValueError as exc:
                await message.reply_text(str(exc))
                return

        image_model = await model("edit")
        image = await generate_image(
            build_image_request(image_model.id, prompt, reply_image)
        )
        user_mention = (
            f"@{update.effective_user.username}"
            if update.effective_user.username
            else f"User {update.effective_user.id}"
        )
        await message.reply_photo(
            io.BytesIO(image),
            caption=f"📝 Requested by {user_mention}\n🎨 Prompt: {prompt}",
        )
    except OpenRouterImageError as exc:
        logger.exception("Edit command failed")
        await message.reply_text(exc.user_message)
        raise HandledCommandError("Edit command failed") from exc
    except (
        httpx2.HTTPError,
        TelegramError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as exc:
        logger.exception("Edit command failed")
        await message.reply_text("AI request failed. Please try again.")
        raise HandledCommandError("Edit command failed") from exc
