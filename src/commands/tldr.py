import html
from urllib.parse import parse_qs, urlparse

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.db import get_db
from config.logger import logger
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# AIDEV-NOTE: Default model for tldr command, can be overridden via /model command
DEFAULT_TLDR_MODEL = "openrouter/x-ai/grok-4-fast"


async def get_tldr_model() -> str:
    """Get the configured AI model for /tldr from database, fallback to default."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT tldr_model FROM group_settings WHERE chat_id = ?",
            (-1,),  # AIDEV-NOTE: Global settings use chat_id = -1
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] else DEFAULT_TLDR_MODEL


def extract_youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    parsed_url = urlparse(url)

    # Handle youtu.be URLs
    if parsed_url.netloc in ("youtu.be", "www.youtu.be"):
        video_id = parsed_url.path[1:]  # Remove leading slash
        return video_id.split("?")[0] if video_id else None

    # Handle all YouTube domains
    youtube_domains = {
        "www.youtube.com",
        "youtube.com",
        "m.youtube.com",
        "www.youtube-nocookie.com",
        "music.youtube.com",
        "gaming.youtube.com",
    }

    if parsed_url.netloc in youtube_domains:
        # Handle /watch URLs
        if parsed_url.path in ("/watch", "/watch_popup"):
            p = parse_qs(parsed_url.query)
            return p.get("v", [None])[0]

        # Handle /embed/, /v/, /shorts/ URLs
        if parsed_url.path.startswith(("/embed/", "/v/", "/shorts/")):
            path_parts = parsed_url.path.split("/")
            return path_parts[2] if len(path_parts) > 2 else None

        # Handle attribution links
        if parsed_url.path == "/attribution_link":
            p = parse_qs(parsed_url.query)
            u_param = p.get("u", [None])[0]
            if u_param and u_param.startswith("/watch?v="):
                return parse_qs(u_param.split("?", 1)[1]).get("v", [None])[0]

    return None


async def get_youtube_transcript(video_id: str) -> str | None:
    """Retrieve transcript from NanoGPT API."""
    headers = {"Content-Type": "application/json"}
    nano_api_key = config["API"].get("NANO_GPT_API_KEY")
    if nano_api_key:
        headers["x-api-key"] = nano_api_key

    payload = {"urls": [f"https://www.youtube.com/watch?v={video_id}"]}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://nano-gpt.com/api/youtube-transcribe",
            headers=headers,
            json=payload,
        ) as response:
            if response.status != 200:
                return None
            data = await response.json()
            transcripts = data.get("transcripts")
            if not transcripts:
                return None
            return transcripts[0].get("transcript")


async def get_cached_youtube_summary(conn, video_id: str) -> str | None:
    """Retrieve cached YouTube summary from the database."""
    async with conn.execute(
        "SELECT summary FROM tldw WHERE video_id = ?;", (video_id,)
    ) as cursor:
        result = await cursor.fetchone()
        return result[0] if result else None


async def cache_youtube_summary(conn, video_id: str, summary: str, user_id: int):
    """Cache the YouTube summary in the database."""
    await conn.execute(
        "INSERT INTO tldw (video_id, summary, user_id) VALUES (?, ?, ?);",
        (video_id, summary, user_id),
    )
    await conn.commit()


async def summarize_text(text: str, context_hint: str = "") -> str:
    """Summarize text using AI."""
    model_name = await get_tldr_model()

    # Strip 'openrouter/' prefix if present
    if model_name.startswith("openrouter/"):
        model_name = model_name[11:]

    context = f" (source: {context_hint})" if context_hint else ""
    system_content = f"""Summarize the following content{context} as a short bullet-point list.

Rules:
- Use 3-6 bullet points maximum
- Each bullet should be one concise sentence capturing a key point
- Focus on the crux: main arguments, conclusions, or takeaways
- Skip fluff, intros, and filler
- No headers or extra formatting, just bullets"""

    headers = {
        "Authorization": f"Bearer {config['API']['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
        "X-Title": "SuperSeriousBot",
        "HTTP-Referer": "https://superserio.us",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": text},
        ],
        "max_tokens": 500,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            OPENROUTER_API_URL, headers=headers, json=payload
        ) as resp:
            resp.raise_for_status()
            response = await resp.json()

    content = response["choices"][0]["message"]["content"]
    return str(content) if content else "No summary available"


@usage("/tldr")
@example("/tldr")
@triggers(["tldr", "tldw"])
@api_key("OPENROUTER_API_KEY")
@description(
    "Generate a TLDR summary. Works with YouTube videos, URLs, or replied message text."
)
async def tldr(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a TLDR for YouTube videos, URLs, or replied text."""
    message = get_message(update)
    if not message or not message.from_user:
        return

    url = utils.extract_link(message)

    if url:
        url_str = url.geturl()

        # Check if it's a YouTube URL
        video_id = extract_youtube_video_id(url_str)
        if video_id:
            # YouTube video - use transcript
            async with get_db(write=True) as conn:
                cached_summary = await get_cached_youtube_summary(conn, video_id)
                if cached_summary:
                    await message.reply_text(
                        cached_summary, parse_mode=ParseMode.MARKDOWN
                    )
                    return

                transcript = await get_youtube_transcript(video_id)
                if not transcript:
                    await message.reply_text(
                        "Could not retrieve transcript for this video."
                    )
                    return

                summary = await summarize_text(
                    f"YouTube transcript:\n\n{transcript}",
                    context_hint="a YouTube video transcript",
                )
                await message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)
                await cache_youtube_summary(
                    conn, video_id, summary, message.from_user.id
                )
            return

        # Non-YouTube URL - use NanoGPT web scraping API
        try:
            headers = {"Content-Type": "application/json"}
            nano_api_key = config["API"].get("NANO_GPT_API_KEY")
            if nano_api_key:
                headers["x-api-key"] = nano_api_key

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://nano-gpt.com/api/scrape-urls",
                    headers=headers,
                    json={"urls": [url_str]},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    print(await response.text())
                    if response.status == 402:
                        await message.reply_text(
                            "Insufficient API balance for web scraping."
                        )
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
                await message.reply_text(f"Failed to scrape URL: {error_msg}")
                return

            raw_text = results[0].get("markdown") or results[0].get("content", "")
            if not raw_text:
                await message.reply_text("No content found at the URL.")
                return

            max_chars = 20000
            if len(raw_text) > max_chars:
                raw_text = raw_text[:max_chars] + "..."

            summary = await summarize_text(
                f"Please create a TLDR summary of this content:\n\n{raw_text}"
            )

            formatted_response = f"<b>TLDR Summary:</b>\n\n{html.escape(summary)}\n\n<b>Source:</b> {html.escape(url_str)}"
            await message.reply_text(
                formatted_response,
                disable_web_page_preview=True,
                parse_mode=ParseMode.HTML,
            )
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching content from {url_str}: {e}")
            await message.reply_text(
                "Failed to fetch content from the URL. Please check if the URL is accessible."
            )
        except Exception as e:
            logger.error(f"Error generating TLDR for {url_str}: {e}")
            await message.reply_text(
                f"An error occurred while generating the summary: {e!s}"
            )
        return

    # No URL found: summarize replied message text (if any)
    source_message = message.reply_to_message
    if not source_message or not (
        getattr(source_message, "text", None)
        or getattr(source_message, "caption", None)
    ):
        await commands.usage_string(message, tldr)
        return

    raw_text = source_message.text or source_message.caption or ""
    username = (
        source_message.from_user.username if source_message.from_user else "unknown"
    )

    try:
        max_chars = 20000
        if len(raw_text) > max_chars:
            raw_text = raw_text[:max_chars] + "..."

        summary = await summarize_text(
            f"Please create a TLDR summary of this message from {username}:\n\n{raw_text}"
        )
        formatted_response = f"<b>TLDR Summary:</b>\n\n{html.escape(summary)}"

        await message.reply_text(
            formatted_response, disable_web_page_preview=True, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error generating TLDR for replied message: {e}")
        await message.reply_text(
            f"An error occurred while generating the summary: {e!s}"
        )
