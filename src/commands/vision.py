from io import BytesIO

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.options import config
from utils.decorators import api_key, description, example, triggers, usage

AZURE_ENDPOINT = "https://tgbot.cognitiveservices.azure.com/"
if "AZURE_API_KEY" in config["API"]:
    computervision_client = ComputerVisionClient(
        AZURE_ENDPOINT, CognitiveServicesCredentials(config["API"]["AZURE_API_KEY"])
    )


@triggers(["age"])
@description("Reply to an image to use AI to estimate the age of a person.")
@usage("/age")
@example("/age")
@api_key("AZURE_API_KEY")
async def age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Guess the age and gender from an image.
    """
    try:
        photo = update.message.photo or update.message.reply_to_message.photo
        file = await context.bot.getFile(photo[-1].file_id)
        buffer = BytesIO(await file.download_as_bytearray())
        buffer.seek(0)

        detect_faces_results = computervision_client.analyze_image_in_stream(
            buffer, ["faces"]
        )

        if len(detect_faces_results.faces) == 0:
            text = "No faces detected."
        else:
            if len(detect_faces_results.faces) == 1:
                face = detect_faces_results.faces[0]
                text = "<b>{}</b> of age {}".format(face.gender, face.age)
            else:
                text = f"{len(detect_faces_results.faces)} faces found:"
                for face in detect_faces_results.faces:
                    text += "\n<b>{}</b> of age {}".format(face.gender, face.age)

        if update.message.reply_to_message:
            await update.message.reply_to_message.reply_text(
                text=text, parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(text=text, parse_mode=ParseMode.HTML)
    except AttributeError:
        await commands.usage_string(update.message, age)
    except IndexError:
        await update.message.reply_text("No photo found.")


@triggers(["caption"])
@description("Reply to an image to use AI to generate a caption for the image.")
@usage("/caption")
@example("/caption")
@api_key("AZURE_API_KEY")
async def caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate a caption for an image.
    """
    try:
        photo = update.message.photo or update.message.reply_to_message.photo
        file = await context.bot.getFile(photo[-1].file_id)
        buffer = BytesIO(await file.download_as_bytearray())
        buffer.seek(0)

        description_results = computervision_client.describe_image_in_stream(buffer)
        description = description_results.captions[0].text
        confidence = description_results.captions[0].confidence

        text = f"{description}.\n<b>Confidence:</b> {round(confidence * 100, 2)}%"
        text = "%s%s" % (text[0].upper(), text[1:])

        if update.message.reply_to_message:
            await update.message.reply_to_message.reply_text(
                text=text, parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(text=text, parse_mode=ParseMode.HTML)
    except AttributeError:
        await commands.usage_string(update.message, caption)
    except IndexError:
        await update.message.reply_text("No photo found.")
