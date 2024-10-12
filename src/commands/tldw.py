from typing import Optional
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

SYSTEM_PROMPT = """
You are a helpful assistant running as a Telegram bot called @SuperSeriousBot. Your task is to summarize the transcript of a YouTube video in a concise, engaging manner suitable for a Telegram message.

Guidelines for your summary:
1. Be concise: Aim for 2-3 short paragraphs (around 150-200 words total).
2. Highlight key points: Focus on the main ideas, key takeaways, and conclusion of the video.
3. Structure your response for easy reading on mobile devices:
   - Use short sentences and paragraphs.
   - Utilize bullet points for listing main ideas if appropriate.
4. End with a short conclusion or takeaway.
5. Use Telegram-compatible Markdown for formatting:
   - *bold* for emphasis
   - _italic_ for titles or quotes
   - `code` for technical terms
   - [text](URL) for links (if mentioned in the video)

Remember, your goal is to provide value to the user quickly and effectively.
"""


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    parsed_url = urlparse(url)
    if parsed_url.netloc == "youtu.be":
        return parsed_url.path[1:]
    if parsed_url.netloc in ("www.youtube.com", "youtube.com"):
        if parsed_url.path == "/watch":
            p = parse_qs(parsed_url.query)
            return p.get("v", [None])[0]
        if parsed_url.path.startswith(("/embed/", "/v/")):
            return parsed_url.path.split("/")[2]
    return None


async def get_transcript(video_id: str) -> Optional[str]:
    """Retrieve and format the transcript for a given video ID."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://youtube-transcripts.p.rapidapi.com/youtube/transcript",
            headers={
                "x-rapidapi-key": config["API"]["RAPID_API_KEY"],
                "x-rapidapi-host": "youtube-transcripts.p.rapidapi.com",
            },
            params={"url": video_url},
        ) as response:
            if response.status != 200:
                return None
            data = await response.json()
            if not data.get("content"):
                return None

            # Join all texts from the transcript
            return " ".join([item["text"] for item in data["content"]])


async def summarize_transcript(transcript: str) -> str:
    """Summarize the given transcript using AI."""
    response = await acompletion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    return response.choices[0].message.content


async def get_cached_summary(conn, video_id: str) -> Optional[str]:
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
@api_key("OPEN_AI_API_KEY")
@example("/tldw https://www.youtube.com/watch?v=xuCn8ux2gbs")
@description("Too Long; Didn't Watch for YouTube videos.")
async def tldw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Too Long; Didn't Watch for YouTube videos"""
    message = update.message
    if not message:
        return

    url = utils.extract_link(message.reply_to_message or message)
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
