import html
import os

import aiohttp
from litellm import acompletion
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.logger import logger
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message

if config["API"]["OPENROUTER_API_KEY"]:
    os.environ["OPENROUTER_API_KEY"] = config["API"]["OPENROUTER_API_KEY"]


@usage("/tldr")
@example("/tldr")
@triggers(["tldr"])
@api_key("OPENROUTER_API_KEY")
@description(
    "Reply to a message or link to generate a TLDR. If no link is found, the replied message text is summarized."
)
async def tldr(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """
    Generate a TLDR for a given URL or replied text using LLM.
    """

    message = message
    url = utils.extract_link(message)

    if url:
        # Summarize content from URL via r.jina.ai
        try:
            jina_url = f"https://r.jina.ai/{url.geturl()}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    jina_url, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    raw_text = await response.text()

            max_chars = 20000
            if len(raw_text) > max_chars:
                raw_text = raw_text[:max_chars] + "..."

            llm_response = await acompletion(
                model="openrouter/x-ai/grok-4-fast",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise summaries. Create a clear, informative TLDR summary of the provided text. Focus on the main points and key information. Make it as short as possible.",
                    },
                    {
                        "role": "user",
                        "content": f"Please create a TLDR summary of this content:\n\n{raw_text}",
                    },
                ],
                extra_headers={
                    "X-Title": "SuperSeriousBot",
                    "HTTP-Referer": "https://superserio.us",
                },
                api_key=config["API"]["OPENROUTER_API_KEY"],
                max_tokens=1000,
            )

            summary = llm_response.choices[0].message.content  # type: ignore
            summary_str = str(summary) if summary else "No summary available"

            formatted_response = f"<b>TLDR Summary:</b>\n\n{html.escape(summary_str)}\n\n<b>Source:</b> {html.escape(url.geturl())}"

            await message.reply_text(
                formatted_response,
                disable_web_page_preview=True,
                parse_mode=ParseMode.HTML,
            )
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching content from {url.geturl()}: {e}")
            await message.reply_text(
                "Failed to fetch content from the URL. Please check if the URL is accessible."
            )
        except Exception as e:
            logger.error(f"Error generating TLDR for {url.geturl()}: {e}")
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

        llm_response = await acompletion(
            model="openrouter/x-ai/grok-4-fast",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise summaries. Create a clear, informative TLDR summary of the provided text. Focus on the main points and key information. Make it as short as possible.",
                },
                {
                    "role": "user",
                    "content": f"Please create a TLDR summary of this message from {username}:\n\n{raw_text}",
                },
            ],
            extra_headers={
                "X-Title": "SuperSeriousBot",
                "HTTP-Referer": "https://superserio.us",
            },
            api_key=config["API"]["OPENROUTER_API_KEY"],
            max_tokens=1000,
        )

        summary = llm_response.choices[0].message.content  # type: ignore
        summary_str = str(summary) if summary else "No summary available"
        formatted_response = f"<b>TLDR Summary:</b>\n\n{html.escape(summary_str)}"

        await message.reply_text(
            formatted_response, disable_web_page_preview=True, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error generating TLDR for replied message: {e}")
        await message.reply_text(
            f"An error occurred while generating the summary: {e!s}"
        )
