import openai
from telegram import Update
from telegram.ext import ContextTypes

import commands
from config import config, logger
from utils.decorators import api_key, description, example, triggers, usage

if "OPEN_AI_API_KEY" in config["API"]:
    openai.api_key = config["API"]["OPEN_AI_API_KEY"]


@triggers(["imagine"])
@api_key("OPEN_AI_API_KEY")
@usage("/imagine [PROMPT]")
@example("/imagine A divorced rhino walks into a dive bar.")
@description("Use OpenAI Dall-E to generate images.")
async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate images using OpenAI Dall-E"""
    if not context.args:
        await commands.usage_string(update.message, imagine)
        return

    prompt = " ".join(context.args)
    logger.info("Generating image for prompt: %s", prompt)

    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="256x256",
        )

        image_url = response["data"][0]["url"]
        await update.message.reply_photo(image_url)
    except openai.error.OpenAIError as e:
        await update.message.reply_text(e.user_message)
        logger.error(e)
