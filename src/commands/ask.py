import openai
from telegram import Update
from telegram.ext import ContextTypes

import commands
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

if config["API"]["OPEN_AI_API_KEY"]:
    openai.api_key = config["API"]["OPEN_AI_API_KEY"]


@triggers(["ask"])
@usage("/ask [query]")
@api_key("OPEN_AI_API_KEY")
@example("/ask How long does a train between Tokyo and Hokkaido take?")
@description("Ask anything using OpenAI's GPT-3.5 Turbo API.")
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask anything using OpenAI's GPT-3.5 Turbo API."""
    if not context.args:
        await commands.usage_string(update.message, ask)
        return

    query: str = " ".join(context.args)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Your goal is to answer one-off questions "
                "from users in a short and brief manner. Keep the answers as detailed "
                "as possible while keeping the response short.",
            },
            {
                "role": "user",
                "content": query,
            },
        ],
    )

    await update.message.reply_text(response.choices[0].message.content)
