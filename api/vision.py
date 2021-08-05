from io import BytesIO
from typing import TYPE_CHECKING

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def age(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Guesses age and gender of people in an image."""
    try:
        if update.message and update.message.reply_to_message:
            message: 'telegram.Message' = update.message.reply_to_message
        else:
            return

        file: telegram.File = context.bot.getFile(message.photo[-1].file_id)
        buffer = BytesIO(file.download_as_bytearray())
        buffer.seek(0)

        api_key = config["AZURE_KEY"]
        endpoint = 'https://tgbot.cognitiveservices.azure.com/'
        computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(api_key))

        detect_faces_results = computervision_client.analyze_image_in_stream(buffer, ["faces"])
        if len(detect_faces_results.faces) == 0:
            text = "No faces detected."
        else:
            if len(detect_faces_results.faces) == 1:
                face = detect_faces_results.faces[0]
                text = "*{}* of age {}".format(face.gender, face.age)
            else:
                text = f"{len(detect_faces_results.faces)} faces found:"
                for face in detect_faces_results.faces:
                    text += "\n*{}* of age {}".format(face.gender, face.age)

        message.reply_text(text=text)
    except AttributeError:
        update.message.reply_text(
            text="*Usage:* `/age`\n"
                 "Type /age in response to an image. Only the first face is considered.\n"
        )


def caption(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Uses NLP to generate a caption for an image."""
    try:
        if update.message and update.message.reply_to_message:
            message: 'telegram.Message' = update.message.reply_to_message
        else:
            return

        file: telegram.File = context.bot.getFile(message.photo[-1].file_id)
        buffer = BytesIO(file.download_as_bytearray())
        buffer.seek(0)

        api_key = config["AZURE_KEY"]
        endpoint = 'https://tgbot.cognitiveservices.azure.com/'
        computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(api_key))

        description_results = computervision_client.describe_image_in_stream(buffer)
        description = description_results.captions[0].text
        confidence = description_results.captions[0].confidence

        text = f"{description}.\n*Confidence:* {round(confidence * 100, 2)}%"
        text = "%s%s" % (text[0].upper(), text[1:])

        message.reply_text(text=text)

    except AttributeError:
        update.message.reply_text(
            text="*Usage:* `/caption`\n"
                 "Type /caption in response to an image.\n"
        )
