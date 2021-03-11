from typing import TYPE_CHECKING, Dict

import cloudmersive_image_api_client
from cloudmersive_image_api_client import Configuration, FaceApi

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def age(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Guesses age and gender of people in an image."""
    text: str
    try:
        if update.message and update.message.reply_to_message:
            message: 'telegram.Message' = update.message.reply_to_message
        else:
            raise AttributeError

        file: telegram.File = context.bot.getFile(message.photo[-1].file_id)
        configuration: Configuration = cloudmersive_image_api_client.Configuration()
        configuration.api_key['Apikey']: Dict = config["CLOUDMERSIVE_API_KEY"]

        api_instance: FaceApi = cloudmersive_image_api_client.FaceApi(
            cloudmersive_image_api_client.ApiClient(configuration))
        file.download('classify.jpg')

        try:
            api_response = api_instance.face_detect_age('classify.jpg')
            text = f'**Age: {round(api_response.people_with_age[0].age, 2)}**\n'
            api_response = api_instance.face_detect_gender('classify.jpg')
            text += f'Gender: {api_response.person_with_gender[0].gender_class}\n'
            text += f'Confidence: {round(api_response.person_with_gender[0].gender_classification_confidence * 100, 2)}%'
        except IndexError:
            text = "Unable to find faces."

        message.reply_text(text=text)
    except AttributeError:
        update.message.reply_text(text="*Usage:* `/age`\n"
                                       "Type /age in response to an image. Only the first face is considered.\n")
