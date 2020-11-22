import cloudmersive_image_api_client
from configuration import config


def caption(update, context):
    """Uses NLP to generate a caption for an image."""
    try:
        message = update.message.reply_to_message

        file = context.bot.getFile(message.photo[-1].file_id)
        configuration = cloudmersive_image_api_client.Configuration()
        configuration.api_key['Apikey'] = config["CLOUDMERSIVE_API_KEY"]

        api_instance = cloudmersive_image_api_client.RecognizeApi(cloudmersive_image_api_client.ApiClient(configuration))
        file.download('classify.jpg')

        try:
            api_response = api_instance.recognize_describe('classify.jpg')
            text = f'{api_response.best_outcome.description}\n'
            text += f'**Confidence:** {round(api_response.best_outcome.confidence_score * 100, 2)}%\n'
        except IndexError:
            text = "Unable to generate a caption."

        message.reply_text(text=text)
    except AttributeError:
        update.message.reply_text(text="*Usage:* `/caption`\n" \
                                       "Type /caption in response to an image.\n")
