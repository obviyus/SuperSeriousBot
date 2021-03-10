from typing import TYPE_CHECKING

import cloudmersive_image_api_client
from cloudmersive_image_api_client import RecognizeApi

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def caption(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Uses NLP to generate a caption for an image."""
    try:
        if update.message:
            message: 'telegram.Message' = update.message
        else:
            return

        message = message.reply_to_message

        file = context.bot.getFile(message.photo[-1].file_id)
        configuration = cloudmersive_image_api_client.Configuration()
        configuration.api_key['Apikey'] = config["CLOUDMERSIVE_API_KEY"]

        api_instance: RecognizeApi = cloudmersive_image_api_client.RecognizeApi(
            cloudmersive_image_api_client.ApiClient(configuration)
        )

        # TODO: Try to pass a BytesIO object instead of downloading the image using
        #       file.download_as_bytearray()
        file.download('classify.jpg')

        try:
            api_response = api_instance.recognize_describe('classify.jpg')
            text: str = f'{api_response.best_outcome.description}\n'
            text += f'**Confidence:** {round(api_response.best_outcome.confidence_score * 100, 2)}%\n'
        except IndexError:
            text: str = "Unable to generate a caption."

        message.reply_text(text=text)

    # TODO: Handle CLOUDMERSIVE response better
    except AttributeError:
        update.message.reply_text(text="*Usage:* `/caption`\n"
                                       "Type /caption in response to an image.\n")
