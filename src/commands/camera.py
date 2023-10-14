from datetime import datetime

import dateparser
import httpx
import telegram.error
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from commands.weather import Point
from config import config
from utils.decorators import api_key, description, example, triggers, usage

WEBCAM_API = "https://api.windy.com/webcams/api/v3/webcams"


@triggers(["camera", "cam"])
@usage("/cam [location]")
@description("Return the latest image from a webcam near the location.")
@example("/cam New Delhi")
@api_key("WINDY_API_KEY")
async def camera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the latest image from a webcam near the location."""
    if not context.args:
        await commands.usage_string(update.message, camera)
        return

    point = Point(" ".join(context.args))
    if not point.found:
        await update.message.reply_text("Could not find location.")
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(
            WEBCAM_API,
            params={
                "nearby": f"{point.latitude},{point.longitude},250",
                "include": "location,images",
                "limit": 1,
            },
            headers={
                "X-WINDY-API-KEY": config["API"]["WINDY_API_KEY"],
            },
        )

    if response.status_code != 200:
        await update.message.reply_text(text="No cameras found.")
        return

    response = response.json()
    if len(response["webcams"]) == 0:
        await update.message.reply_text(text="No cameras found.")
        return

    webcam = response["webcams"][0]

    try:
        time_since_update = (
            datetime.now().timestamp()
            - dateparser.parse(webcam["lastUpdatedOn"]).timestamp()
        )
        await update.message.reply_photo(
            photo=webcam["images"]["current"]["preview"],
            caption=f'📹 <b>{webcam["title"]}</b> ({webcam["status"]})'
            f"\n\n🕒 Last updated: {int(time_since_update / 60)} minutes ago"
            f'\n📍 {webcam["location"]["city"]} (<i>{webcam["location"]["latitude"]}, '
            f'{webcam["location"]["longitude"]}</i>)',
            parse_mode=ParseMode.HTML,
        )
    except telegram.error.BadRequest:
        await update.message.reply_text(
            text="Something went wrong while sending the image. Try again later."
        )
        return
