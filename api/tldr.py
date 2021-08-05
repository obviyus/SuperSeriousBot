from typing import Any, Dict, TYPE_CHECKING

import requests
from telegram import MessageEntity

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def tldr(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Generate TLDR of any message or article"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    try:
        content = message.reply_to_message.text

        API_ENDPOINT: str = "https://api.smmry.com/"
        params: Dict[str, Any] = {"SM_API_KEY": config["SMMRY_API_KEY"], "SM_LENGTH": 2}

        if len(message.reply_to_message.parse_entities([MessageEntity.URL]).values()) == 1:
            content_url = message.reply_to_message.parse_entities([MessageEntity.URL]).values()
            params.update({"SM_URL": content_url, "SM_LENGTH": 3})

            r = requests.post(url=API_ENDPOINT, params=params).json()
        else:
            content = content.replace('\r', '. ').replace('\n', '. ')

            sentences: int = content.count(".")
            if sentences <= 3:
                text = "Content too short."
                message.reply_text(text=text)

                return
            else:
                data: Dict[str, str] = {"sm_api_input": content}
                header_params: Dict[str, str] = {"Expect": "100-continue"}
                r = requests.post(url=API_ENDPOINT, params=params, data=data, headers=header_params).json()

        try:
            text = r["sm_api_content"]
            text += f"""\n\n**Content reduced by {r["sm_api_content_reduced"]}**"""
        except KeyError:
            text = "Content too short."

    # If parent message is empty
    except AttributeError:
        text = "*Usage:* `/tldr` in reply to a message or link.\n\nOnly works for 3 or more sentences."

    message.reply_text(text=text)
