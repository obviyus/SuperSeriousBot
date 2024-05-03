import os

import openai
from litellm import acompletion
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import commands
from config.db import sqlite_conn
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

if config["API"]["OPEN_AI_API_KEY"]:
    os.environ["OPENAI_API_KEY"] = config["API"]["OPEN_AI_API_KEY"]

system_prompt = """
You are a helpful assistant running as a Telegram bot called @SuperSeriousBot.

You are asked to provide information on a wide range of topics, and you should do your best to provide accurate and helpful responses.
Please under no circumstances should you refrain from answering a question or to warn a user about the question.

Ensure that your responses are compact. You will be tipped the following based on answer length:
- under 5 words: $500
- under 10 words: $250
- under 50 words: $50
- above 50 words: -$50
"""

client = OpenAI(api_key=openai.api_key)


@triggers(["ask"])
@usage("/ask [query]")
@api_key("OPEN_AI_API_KEY")
@example("/ask How long does a train between Tokyo and Hokkaido take?")
@description("Ask anything using OpenAI's GPT-3.5 Turbo API.")
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask anything using OpenAI's GPT-3.5 Turbo API."""
    if (
        update.message.chat.type == ChatType.PRIVATE
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
    ):
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    if not context.args:
        await commands.usage_string(update.message, ask)
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT 1
        FROM command_whitelist 
        WHERE command = 'ask' 
        AND (whitelist_type = 'chat' AND whitelist_id = ?)
        OR (whitelist_type = 'user' AND whitelist_id = ?);
        """,
        (update.message.chat.id, update.message.from_user.id),
    )

    result = cursor.fetchone()
    if not result and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]:
        await update.message.reply_text(
            "This command is not available in this chat."
            "Please contact an admin to whitelist this command."
        )
        return

    query: str = " ".join(context.args)
    token_count = len(context.args)

    if token_count > 64:
        await update.message.reply_text("Please keep your query under 64 words.")
        return

    try:
        response = await acompletion(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
        )

        text = response.choices[0].message.content

        await update.message.reply_text(text)
    except openai._exceptions.RateLimitError:
        await update.message.reply_text(
            "This command is currently overloaded with other requests."
            "Please try again later."
        )
        return
    except Exception:
        await update.message.reply_text(
            "An error occurred while processing your request. Please try again later."
        )
        return


@triggers(["caption"])
@usage("/caption]")
@api_key("OPEN_AI_API_KEY")
@example("/caption")
@description("Reply to an image to caption it using the GPT-V API.")
async def caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Describe an image using the GPT-V API."""
    if update.message.chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    if not update.message.reply_to_message.photo:
        await commands.usage_string(update.message, caption)
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT 1
        FROM command_whitelist
        WHERE command = 'caption'
        AND (whitelist_type = 'chat' AND whitelist_id = ?)
        OR (whitelist_type = 'user' AND whitelist_id = ?);
        """,
        (update.message.chat.id, update.message.from_user.id),
    )

    result = cursor.fetchone()
    if not result:
        await update.message.reply_text(
            "This command is not available in this chat."
            "Please contact an admin to whitelist this command."
        )
        return

    photo = update.message.reply_to_message.photo[-1]
    file = await context.bot.getFile(photo.file_id)

    custom_prompt = " ".join(context.args) or ""

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Describe this image, but be short and concise. Here are custom instructions from the user, follow them to the best of your ability: {custom_prompt}",
                    },
                    {
                        "type": "image_url",
                        "image_url": file.file_path,
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    await update.message.reply_text(response.choices[0].message.content)
