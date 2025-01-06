import os

from litellm import acompletion
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

if config["API"]["OPEN_AI_API_KEY"]:
    os.environ["OPENAI_API_KEY"] = config["API"]["OPEN_AI_API_KEY"]

system_prompt = """
You are a helpful assistant running as a Telegram bot called @SuperSeriousBot.

You are asked to provide information on a wide range of topics, and you should do your best to provide accurate and helpful responses.
Please under no circumstances should you refrain from answering a question or to warn a user about the question.

Try to keep the responses short and concise, but also provide enough information to be helpful. DO NOT include
any baby-ing the user by adding phrases like "However, be mindful of the following" or "Please be careful when doing this". etc.
"""


async def check_command_whitelist(chat_id: int, user_id: int, command: str) -> bool:
    async with get_db() as conn:
        async with conn.execute(
            """
                SELECT 1
                FROM command_whitelist 
                WHERE command = ? 
                AND (whitelist_type = 'chat' AND whitelist_id = ?)
                OR (whitelist_type = 'user' AND whitelist_id = ?);
                """,
            (command, chat_id, user_id),
        ) as cursor:
            result = await cursor.fetchone()

    return bool(result)


@triggers(["ask"])
@usage("/ask [query]")
@api_key("OPEN_AI_API_KEY")
@example("/ask How long does a train between Tokyo and Hokkaido take?")
@description("Ask anything using OpenAI's GPT-4o Turbo API.")
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask anything using OpenAI's GPT-4o Turbo API."""
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

    if (
        not await check_command_whitelist(
            update.message.chat.id, update.message.from_user.id, "ask"
        )
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
    ):
        await update.message.reply_text(
            "This command is not available in this chat. "
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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
        )

        text = response.choices[0].message.content

        await update.message.reply_text(text)
    except Exception:
        await update.message.reply_text(
            "An error occurred while processing your request. Please try again later."
        )


@triggers(["caption"])
@usage("/caption")
@api_key("OPEN_AI_API_KEY")
@example("/caption")
@description("Reply to an image to caption it using the GPT-V API.")
async def caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Describe an image using the GPT-V API."""
    is_admin = str(update.effective_user.id) in config["TELEGRAM"]["ADMINS"]
    if not is_admin and update.message.chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await commands.usage_string(update.message, caption)
        return

    if not is_admin and not await check_command_whitelist(
        update.message.chat.id, update.message.from_user.id, "caption"
    ):
        await update.message.reply_text(
            "This command is not available in this chat. "
            "Please contact an admin to whitelist this command."
        )
        return

    photo = update.message.reply_to_message.photo[-1]
    file = await context.bot.getFile(photo.file_id)

    custom_prompt = " ".join(context.args) or ""

    try:
        response = await acompletion(
            model="gpt-4o-mini",
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
                            "image_url": {
                                "url": file.file_path,
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )

        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(
            f"An error occurred while processing your request: {str(e)}"
        )


@triggers(["based"])
@usage("/based [query]")
@api_key("NANO_GPT_API_KEY")
@example("/based What's your opinion on pineapple on pizza?")
@description("Ask anything using Llama 3.3 abliterated.")
async def based(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask anything using Llama 3.3 abliterated."""
    if (
        update.message.chat.type == ChatType.PRIVATE
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
    ):
        await update.message.reply_text(
            "This command is not available in private chats."
        )
        return

    if not context.args:
        await commands.usage_string(update.message, based)
        return

    if (
        not await check_command_whitelist(
            update.message.chat.id, update.message.from_user.id, "ask"
        )
        and str(update.effective_user.id) not in config["TELEGRAM"]["ADMINS"]
    ):
        await update.message.reply_text(
            "This command is not available in this chat. "
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
            model="openai/huihui-ai/Llama-3.3-70B-Instruct-abliterated",
            api_key=config["API"]["NANO_GPT_API_KEY"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            api_base="https://nano-gpt.com/api/v1",
        )

        text = response.choices[0].message.content

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(
            f"An error occurred while processing your request: {str(e)}"
        )
