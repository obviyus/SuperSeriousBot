from __future__ import print_function
import cloudmersive_image_api_client
from configuration import config


def age(update, context):
    """Guesses age and gender of people in an image."""
    try:
        message = update.message.reply_to_message

        file = context.bot.getFile(message.photo[-1].file_id)
        configuration = cloudmersive_image_api_client.Configuration()
        configuration.api_key['Apikey'] = config["CLOUDMERSIVE_API_KEY"]

        api_instance = cloudmersive_image_api_client.FaceApi(cloudmersive_image_api_client.ApiClient(configuration))
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
        update.message.reply_text(text="*Usage:* `/age`\n" \
                                       "Type /age in response to an image. Only the first face is considered.\n")
