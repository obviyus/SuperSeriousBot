import html

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config.logger import logger
from config.options import config

SMMRY_API_ENDPOINT: str = "https://api.smmry.com/"


async def tldr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate a TLDR for a given URL.
    """
    url = utils.extract_link(update)

    if not url:
        await utils.usage_string(update.message)
        return

    response = requests.post(
        url=SMMRY_API_ENDPOINT,
        params={
            "SM_API_KEY": config["API"]["SMMRY_API_KEY"],
            "SM_LENGTH": 3,
            "SM_URL": url,
        },
    ).json()

    if "sm_api_error" in response:
        logger.error(f"Error: {response['sm_api_error']}")
        await update.message.reply_text(response["sm_api_error"])
        return

    await update.message.reply_text(
        f"""{html.escape(response["sm_api_content"])}\n\n<b>Content reduced by {response["sm_api_content_reduced"]}</b>""",
        parse_mode=ParseMode.HTML,
    )
