import os
from urllib.parse import parse_qs, urlparse

import aiohttp
from litellm import acompletion
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config import config
from config.db import get_db
from utils.decorators import api_key, description, example, triggers, usage

if config["API"]["OPENROUTER_API_KEY"]:
    os.environ["OPENROUTER_API_KEY"] = config["API"]["OPENROUTER_API_KEY"]


def extract_video_id(url: str) -> str | None:
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


async def get_transcript(video_id: str) -> str | None:
    """Retrieve transcript from NanoGPT API."""
    headers = {"Content-Type": "application/json"}
    api_key = config["API"].get("NANO_GPT_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

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


async def summarize_transcript(transcript: str) -> str:
    """Summarize the given transcript using AI."""
    # Generate summary using LLM
    llm_response = await acompletion(
        model="openrouter/x-ai/grok-4-fast",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that creates concise summaries. Create a clear, informative TLDR summary of the provided text, which is a YouTube video transcript. Focus on the main points and key information. Make it as short as possible.",
            },
            {
                "role": "user",
                "content": f"YouTube transcript:\n\n{transcript}",
            },
        ],
        extra_headers={
            "X-Title": "SuperSeriousBot",
            "HTTP-Referer": "https://superserio.us",
        },
        api_key=config["API"]["OPENROUTER_API_KEY"],
        max_tokens=1000,
    )
    return llm_response.choices[0].message.content


async def get_cached_summary(conn, video_id: str) -> str | None:
    """Retrieve cached summary from the database."""
    async with conn.execute(
        "SELECT summary FROM tldw WHERE video_id = ?;", (video_id,)
    ) as cursor:
        result = await cursor.fetchone()
        return result[0] if result else None


async def cache_summary(conn, video_id: str, summary: str, user_id: int):
    """Cache the summary in the database."""
    await conn.execute(
        "INSERT INTO tldw (video_id, summary, user_id) VALUES (?, ?, ?);",
        (video_id, summary, user_id),
    )
    await conn.commit()


@triggers(["tldw"])
@usage("/tldw [YOUTUBE_URL]")
@api_key("OPENROUTER_API_KEY")
@example("/tldw https://www.youtube.com/watch?v=xuCn8ux2gbs")
@description("Too Long; Didn't Watch for YouTube videos.")
async def tldw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Too Long; Didn't Watch for YouTube videos"""
    message = update.message
    if not message:
        return

    url = utils.extract_link(message)
    if not url:
        await message.reply_text("Please provide a valid YouTube URL to summarize.")
        return

    video_id = extract_video_id(url.geturl())
    if not video_id:
        await message.reply_text(
            "Invalid YouTube URL. Please provide a valid YouTube video link."
        )
        return

    async with get_db(write=True) as conn:
        cached_summary = await get_cached_summary(conn, video_id)
        if cached_summary:
            await message.reply_text(cached_summary, parse_mode=ParseMode.MARKDOWN)
            return

        transcript = await get_transcript(video_id)
        if not transcript:
            await message.reply_text("Could not retrieve transcript for this video.")
            return

        summary = await summarize_transcript(transcript)
        await message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)

        await cache_summary(conn, video_id, summary, message.from_user.id)
