import asyncio
import mimetypes
import os
import subprocess
import tempfile

import ai
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import commands
from commands.ai import generate_text
from commands.runtime import ensure_command_available
from config.logger import logger
from config.options import config
from utils.command_limits import ensure_quota
from utils.decorators import command
from utils.messages import get_message, reply_markdown_or_plain

FALLBACK_PROMPT = "Please transcribe this audio file. No wall of text, keep it readable, suitable for a Telegram message. Begin transcript immediately without any commentary."


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


@command(
    triggers=["tr"],
    usage="/tr [optional instructions]",
    example="/tr Please summarize with bullet points",
    description="Reply to an audio message to have it transcribed using AI.",
    api_key="OPENROUTER_API_KEY",
)
async def transcribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not message.from_user or not update.effective_user:
        return

    if not await ensure_command_available(message, message.from_user.id, "tr"):
        return
    if not await ensure_quota(message, message.from_user.id, "tr"):
        return

    reply = message.reply_to_message
    if not reply:
        await commands.usage_string(message, transcribe)
        return
    if reply.voice:
        file_id = reply.voice.file_id
        mime_type = reply.voice.mime_type
        source_summary = "voice message"
    elif reply.audio:
        file_id = reply.audio.file_id
        mime_type = reply.audio.mime_type
        source_summary = "audio file"
    elif (
        reply.document
        and reply.document.mime_type
        and reply.document.mime_type.startswith("audio/")
    ):
        file_id = reply.document.file_id
        mime_type = reply.document.mime_type
        source_summary = "audio document"
    else:
        await commands.usage_string(message, transcribe)
        return

    api_key_value = config.API.OPENROUTER_API_KEY
    if not api_key_value:
        await message.reply_text("Transcription is not configured.")
        return

    try:
        telegram_file = await context.bot.getFile(file_id)
        audio_bytes = bytes(await telegram_file.download_as_bytearray())
    except TelegramError as exc:  # pragma: no cover - Telegram I/O
        logger.exception("Failed to download audio for transcription: %s", exc)
        await message.reply_text("I couldn't download that audio.")
        return

    suffix = (
        os.path.splitext(telegram_file.file_path)[1]
        if telegram_file.file_path and os.path.splitext(telegram_file.file_path)[1]
        else mimetypes.guess_extension(mime_type or "audio/ogg") or ".ogg"
    )

    try:
        wav_audio = await _convert_audio_to_wav(audio_bytes, suffix)
    except RuntimeError as exc:
        logger.exception("Failed to convert audio for transcription: %s", exc)
        await message.reply_text("I couldn't process that audio.")
        return

    user_prompt = " ".join(context.args).strip() if context.args else ""
    instruction = user_prompt or FALLBACK_PROMPT

    try:
        transcript = await generate_text(
            "tr",
            [
                ai.user_message(
                    f"You are transcribing a {source_summary}. {instruction}".strip(),
                    ai.file_part(wav_audio, media_type="audio/wav"),
                )
            ],
        )
    except (ai.AIError, TimeoutError, TypeError, ValueError):
        logger.exception("Transcription request failed")
        await message.reply_text("Transcription failed. Please try again.")
        return

    transcript = transcript.strip()
    if not transcript:
        await message.reply_text("No transcript was returned. Please try again.")
        return

    await reply_markdown_or_plain(
        message,
        transcript,
        disable_web_page_preview=True,
        document_name="transcript.txt",
    )
