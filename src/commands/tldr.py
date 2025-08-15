import html
import os

import requests
from litellm import acompletion
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils

from config.logger import logger
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

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
    """
    Generate a TLDR for a given URL or replied text using LLM.
    """

    message = update.message
    url = utils.extract_link(message)

    if url:
        # Summarize content from URL via r.jina.ai
        try:
            jina_url = f"https://r.jina.ai/{url.geturl()}"
            response = requests.get(jina_url, timeout=30)
            response.raise_for_status()

            raw_text = response.text

            max_chars = 20000
            if len(raw_text) > max_chars:
                raw_text = raw_text[:max_chars] + "..."

            llm_response = await acompletion(
                model="openrouter/google/gemini-2.5-flash",
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
                    "HTTP-Referer": "https://t.me/SuperSeriousBot",
                },
                api_key=config["API"]["OPENROUTER_API_KEY"],
                max_tokens=1000,
            )

            summary = llm_response.choices[0].message.content

            formatted_response = f"<b>TLDR Summary:</b>\n\n{html.escape(summary)}\n\n<b>Source:</b> {html.escape(url.geturl())}"

            await message.reply_text(
                formatted_response,
                disable_web_page_preview=True,
                parse_mode=ParseMode.HTML,
            )
        except requests.RequestException as e:
            logger.error(f"Error fetching content from {url.geturl()}: {e}")
            await message.reply_text(
                "Failed to fetch content from the URL. Please check if the URL is accessible."
            )
        except Exception as e:
            logger.error(f"Error generating TLDR for {url.geturl()}: {e}")
            await message.reply_text(
                f"An error occurred while generating the summary: {str(e)}"
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

    try:
        max_chars = 20000
        if len(raw_text) > max_chars:
            raw_text = raw_text[:max_chars] + "..."

        llm_response = await acompletion(
            model="openrouter/google/gemini-2.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise summaries. Create a clear, informative TLDR summary of the provided text. Focus on the main points and key information. Make it as short as possible.",
                },
                {
                    "role": "user",
                    "content": f"Please create a TLDR summary of this message from {source_message.from_user.username}:\n\n{raw_text}",
                },
            ],
            extra_headers={
                "X-Title": "SuperSeriousBot",
                "HTTP-Referer": "https://t.me/SuperSeriousBot",
            },
            api_key=config["API"]["OPENROUTER_API_KEY"],
            max_tokens=1000,
        )

        summary = llm_response.choices[0].message.content
        formatted_response = f"<b>TLDR Summary:</b>\n\n{html.escape(summary)}"

        await message.reply_text(
            formatted_response, disable_web_page_preview=True, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error generating TLDR for replied message: {e}")
        await message.reply_text(
            f"An error occurred while generating the summary: {str(e)}"
        )
