import asyncio
import base64
import mimetypes
import os
import subprocess
import tempfile
from typing import NamedTuple

import aiohttp
from telegram import Message, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import commands
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message

from .ask import check_command_whitelist, get_tr_model

FALLBACK_PROMPT = "Please transcribe this audio file. No wall of text, keep it readable, suitable for a Telegram message. Begin transcript immediately without any commentary."


class AudioSource(NamedTuple):
    file_id: str
    mime_type: str | None
    summary: str


def _guess_suffix(mime_type: str | None, file_path: str | None) -> str:
    if file_path:
        _, ext = os.path.splitext(file_path)
        if ext:
            return ext
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed
    return ".ogg"


async def _convert_audio_to_wav(
    audio_bytes: bytes, suffix: str
) -> bytes:  # pragma: no cover - thin subprocess wrapper
    def _run() -> bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as src:
            src.write(audio_bytes)
            src_path = src.name

        dst_fd, dst_path = tempfile.mkstemp(suffix=".wav")
        os.close(dst_fd)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    src_path,
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    dst_path,
                ],
                capture_output=True,
                check=True,
            )
            with open(dst_path, "rb") as dst_file:
                return dst_file.read()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg is required to transcode audio for transcription."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"ffmpeg failed to process the audio: {stderr}") from exc
        finally:
            os.unlink(src_path)
            if os.path.exists(dst_path):
                os.unlink(dst_path)

    return await asyncio.to_thread(_run)


def _extract_audio_source(message: Message) -> AudioSource | None:
    reply = message.reply_to_message
    if not reply:
        return None

    if reply.voice:
        return AudioSource(reply.voice.file_id, reply.voice.mime_type, "voice message")
    if reply.audio:
        return AudioSource(reply.audio.file_id, reply.audio.mime_type, "audio file")
    if (
        reply.document
        and reply.document.mime_type
        and reply.document.mime_type.startswith("audio/")
    ):
        return AudioSource(
            reply.document.file_id,
            reply.document.mime_type,
            "audio document",
        )
    return None


def _extract_text_from_response(data: dict) -> str | None:
    choices = data.get("choices") or []
    if not choices:
        return None

    content = choices[0].get("message", {}).get("content")
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if text:
                    parts.append(text)
        combined = "\n".join(parts).strip()
        return combined or None
    return None


@triggers(["tr"])
@example("/tr Please summarize with bullet points")
@usage("/tr [optional instructions]")
@description("Reply to an audio message to have it transcribed via OpenRouter.")
@api_key("OPENROUTER_API_KEY")
async def transcribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not message.from_user or not update.effective_user:
        return

    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]

    if not is_admin and message.chat.type == ChatType.PRIVATE:
        await message.reply_text("This command is not available in private chats.")
        return

    audio_source = _extract_audio_source(message)
    if not audio_source:
        await commands.usage_string(message, transcribe)
        return

    if not is_admin and not await check_command_whitelist(
        message.chat.id, message.from_user.id, "tr"
    ):
        await message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command.",
        )
        return

    api_key_value = config["API"].get("OPENROUTER_API_KEY")
    if not api_key_value:
        await message.reply_text("OPENROUTER_API_KEY is required to use this command.")
        return

    try:
        telegram_file = await context.bot.getFile(audio_source.file_id)
        audio_bytes = bytes(await telegram_file.download_as_bytearray())
    except Exception as exc:  # pragma: no cover - Telegram I/O
        await message.reply_text(f"Failed to download the audio message: {exc!s}")
        return

    suffix = _guess_suffix(audio_source.mime_type, telegram_file.file_path)

    try:
        wav_audio = await _convert_audio_to_wav(audio_bytes, suffix)
    except RuntimeError as exc:
        await message.reply_text(str(exc))
        return

    base64_audio = base64.b64encode(wav_audio).decode("utf-8")
    user_prompt = " ".join(context.args).strip() if context.args else ""
    instruction = user_prompt or FALLBACK_PROMPT

    # Get configured model from database
    model_name = await get_tr_model()

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"You are transcribing a {audio_source.summary}. "
                            f"{instruction}"
                        ).strip(),
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"data": base64_audio, "format": "wav"},
                    },
                ],
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key_value}",
        "Content-Type": "application/json",
        "X-Title": "SuperSeriousBot",
        "HTTP-Referer": "https://superserio.us",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                await message.reply_text(
                    f"OpenRouter request failed ({response.status}): {error_text}"
                )
                return

            data = await response.json()

    transcript = _extract_text_from_response(data)
    if not transcript:
        await message.reply_text("Received an empty response from the AI.")
        return

    await message.reply_text(transcript, disable_web_page_preview=True)
