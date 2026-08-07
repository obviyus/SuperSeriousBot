import html
from urllib.parse import parse_qs, urlparse

import ai
from telegram import Document, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ExtBot

import commands
import utils
from commands.ai import generate_text
from commands.runtime import ensure_command_available
from config.db import get_db
from config.logger import logger
from config.options import config
from utils.command_limits import ensure_quota
from utils.decorators import command
from utils.messages import get_message, reply_markdown_or_plain

MAX_DOCUMENT_BYTES = 2_000_000


async def read_text_document(bot: ExtBot, document: Document) -> str | None:
    """Return a document's contents as text, or None if it isn't text."""
    telegram_file = await bot.getFile(document.file_id)
    data = bytes(await telegram_file.download_as_bytearray())
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def extract_youtube_video_id(url: str) -> str | None:
    parsed_url = urlparse(url)
    netloc = parsed_url.netloc.removeprefix("www.")

    if netloc == "youtu.be":
        return parsed_url.path.lstrip("/").split("?", 1)[0] or None
    if netloc not in {
        "youtube.com",
        "m.youtube.com",
        "youtube-nocookie.com",
        "music.youtube.com",
        "gaming.youtube.com",
    }:
        return None
    if parsed_url.path in {"/watch", "/watch_popup"}:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    if parsed_url.path.startswith(("/embed/", "/v/", "/shorts/")):
        path_parts = parsed_url.path.split("/", 3)
        return path_parts[2] if len(path_parts) > 2 else None
    if parsed_url.path != "/attribution_link":
        return None
    u_param = parse_qs(parsed_url.query).get("u", [None])[0]
    if u_param and u_param.startswith("/watch?v="):
        return parse_qs(u_param.split("?", 1)[1]).get("v", [None])[0]
    return None


async def summarize_text(text: str, context_hint: str = "") -> str:
    """Summarize text using AI."""
    import ai

    context = f" (source: {context_hint})" if context_hint else ""
    system_content = f"""Summarize the following content{context} as a short bullet-point list.

Rules:
- Use 3-6 bullet points maximum
- Each bullet should be one concise sentence capturing a key point
- Focus on the crux: main arguments, conclusions, or takeaways
- Skip fluff, intros, and filler
- No headers or extra formatting, just bullets"""

    content = await generate_text(
        "tldr",
        [
            ai.system_message(system_content),
            ai.user_message(text),
        ],
        max_tokens=500,
    )
    return content or "No summary available"


@command(
    triggers=["tldr", "tldw"],
    usage="/tldr",
    example="/tldr",
    description="Generate a TLDR summary. Works with YouTube videos, URLs, replied message text, or text files.",
    api_key="OPENROUTER_API_KEY",
)
async def tldr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a TLDR for YouTube videos, URLs, replied text, or text files."""
    import aiohttp

    message = get_message(update)
    if not message or not message.from_user:
        return

    if not await ensure_command_available(message, message.from_user.id, "tldr"):
        return
    if not await ensure_quota(message, message.from_user.id, "tldr"):
        return

    url = utils.extract_link(message)

    if url:
        url_str = url.geturl()

        # Check if it's a YouTube URL
        video_id = extract_youtube_video_id(url_str)
        if video_id:
            try:
                async with (
                    get_db() as conn,
                    conn.execute(
                        "SELECT summary FROM tldw WHERE video_id = ?;",
                        (video_id,),
                    ) as cursor,
                ):
                    cached_summary = await cursor.fetchone()
                if cached_summary:
                    await reply_markdown_or_plain(message, cached_summary[0])
                    return

                headers = {"Content-Type": "application/json"}
                nano_api_key = config.API.NANO_GPT_API_KEY
                if nano_api_key:
                    headers["x-api-key"] = nano_api_key

                async with (
                    aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as session,
                    session.post(
                        "https://nano-gpt.com/api/youtube-transcribe",
                        headers=headers,
                        json={"urls": [f"https://www.youtube.com/watch?v={video_id}"]},
                    ) as response,
                ):
                    if response.status != 200:
                        await message.reply_text(
                            "Could not retrieve transcript for this video."
                        )
                        return
                    data = await response.json()
                transcripts = data.get("transcripts")
                if not transcripts or not transcripts[0].get("transcript"):
                    await message.reply_text(
                        "Could not retrieve transcript for this video."
                    )
                    return

                summary = await summarize_text(
                    f"YouTube transcript:\n\n{transcripts[0]['transcript']}",
                    context_hint="a YouTube video transcript",
                )
                await reply_markdown_or_plain(message, summary)
                async with get_db() as conn:
                    await conn.execute(
                        "INSERT INTO tldw (video_id, summary, user_id) VALUES (?, ?, ?);",
                        (video_id, summary, message.from_user.id),
                    )
                return
            except (
                ai.AIError,
                aiohttp.ClientError,
                KeyError,
                RuntimeError,
                TimeoutError,
                TypeError,
                ValueError,
            ) as e:
                logger.error("Error generating YouTube TLDR for %s: %s", video_id, e)
                await message.reply_text("I couldn't generate a summary for that.")
                return

        try:
            headers = {"Content-Type": "application/json"}
            nano_api_key = config.API.NANO_GPT_API_KEY
            if nano_api_key:
                headers["x-api-key"] = nano_api_key

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    "https://nano-gpt.com/api/scrape-urls",
                    headers=headers,
                    json={"urls": [url_str]},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response,
            ):
                if response.status == 402:
                    await message.reply_text("I couldn't read that URL right now.")
                    return
                response.raise_for_status()
                data = await response.json()

            results = data.get("results", [])
            if not results or not results[0].get("success"):
                error_msg = (
                    results[0].get("error", "Unknown error")
                    if results
                    else "No results"
                )
                logger.error("URL scrape failed for %s: %s", url_str, error_msg)
                await message.reply_text("I couldn't read that URL.")
                return

            raw_text = results[0].get("markdown") or results[0].get("content", "")
            if not raw_text:
                await message.reply_text("No content found at the URL.")
                return
            summary_prompt = "Please create a TLDR summary of this content:"
            response_suffix = f"\n\n<b>Source:</b> {html.escape(url_str)}"
            error_subject = url_str
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching content from {url_str}: {e}")
            await message.reply_text(
                "Failed to fetch content from the URL. Please check if the URL is accessible."
            )
            return
    else:
        source_message = message.reply_to_message
        if not source_message:
            await commands.usage_string(message, tldr)
            return

        username = (
            source_message.from_user.username if source_message.from_user else "unknown"
        )
        response_suffix = ""

        if document := source_message.document:
            if (document.file_size or 0) > MAX_DOCUMENT_BYTES:
                await message.reply_text("That file is too big to summarize.")
                return
            try:
                file_text = await read_text_document(context.bot, document)
            except TelegramError as e:
                logger.error("Error downloading %s: %s", document.file_name, e)
                await message.reply_text("I couldn't download that file.")
                return
            if file_text is None:
                await message.reply_text("I can only summarize text files.")
                return
            if not file_text.strip():
                await message.reply_text("That file is empty.")
                return
            raw_text = file_text
            summary_prompt = (
                f"Please create a TLDR summary of this file "
                f"named {document.file_name} shared by {username}:"
            )
            error_subject = "document"
        elif source_message.text or source_message.caption:
            raw_text = source_message.text or source_message.caption or ""
            summary_prompt = (
                f"Please create a TLDR summary of this message from {username}:"
            )
            error_subject = "replied message"
        else:
            await commands.usage_string(message, tldr)
            return

    try:
        if len(raw_text) > 20000:
            raw_text = raw_text[:20000] + "..."
        summary = await summarize_text(f"{summary_prompt}\n\n{raw_text}")
        await message.reply_text(
            f"<b>TLDR Summary:</b>\n\n{html.escape(summary)}{response_suffix}",
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )
    except (
        ai.AIError,
        aiohttp.ClientError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as e:
        logger.error(f"Error generating TLDR for {error_subject}: {e}")
        await message.reply_text("I couldn't generate a summary for that.")
