from typing import TYPE_CHECKING, Dict

import requests
import re

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

import logging


def tldr(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Generate TLDR of any message or article"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    content: str

    try:
        content: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
    except AttributeError as e:
        text = "*Usage:* `/tldr` in reply to a message or link.\n\nOnly works for 3 or more sentences."
        message.reply_text(text=text)

        return

    match = re.search(r"(?P<url>https?://[^\s]+)", content)

    base_url: str = "https://api.smmry.com/"
    params: Dict[str, str] = {"SM_API_KEY": config["SMMRY_API_KEY"], "SM_LENGTH": 3}

    try:
        params.update({"SM_URL": match.group("url")})
        r = requests.post(url=base_url, params=params).json()
    except AttributeError:
        content = content.replace('\r', '').replace('\n', '')

        sentences: int = content.count(".")
        if sentences <= 3:
            message.reply_text(text="Content too short.")
            return

        data: Dict[str, str] = {"sm_api_input": content}
        logging.error(content)
        header_params: Dict[str, str] = {"Expect": "100-continue"}
        r = requests.post(url=base_url, params=params, data=data, headers=header_params).json()

    try:
        text = r["sm_api_content"]
        text += f"""\n\n**Content reduced by {r["sm_api_content_reduced"]}**"""

        message.reply_text(text=text)
    except KeyError:
        message.reply_text(text="Content too short.")
