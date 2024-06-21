from datetime import datetime

import aiohttp
import dateparser
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
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

    webcam = await _get_webcam(point.latitude, point.longitude)
    if not webcam:
        await update.message.reply_text("No cameras found.")
        return

    try:
        await _send_webcam_image(update, webcam)
    except BadRequest:
        await update.message.reply_text(
            "Something went wrong while sending the image. Try again later."
        )


async def _get_webcam(latitude: float, longitude: float) -> dict:
    """Fetch webcam data from Windy API."""
    params = {
        "nearby": f"{latitude},{longitude},250",
        "include": "location,images",
        "limit": 1,
    }
    headers = {"X-WINDY-API-KEY": config["API"]["WINDY_API_KEY"]}

    async with aiohttp.ClientSession() as session:
        async with session.get(WEBCAM_API, params=params, headers=headers) as response:
            if response.status != 200:
                return None
            data = await response.json()
            return data["webcams"][0] if data["webcams"] else None


async def _send_webcam_image(update: Update, webcam: dict) -> None:
    """Send webcam image with caption."""
    time_since_update = (
        datetime.now().timestamp()
        - dateparser.parse(webcam["lastUpdatedOn"]).timestamp()
    )

    caption = (
        f'📹 <b>{webcam["title"]}</b> ({webcam["status"]})\n\n'
        f"🕒 Last updated: {int(time_since_update / 60)} minutes ago\n"
        f'📍 {webcam["location"]["city"]} '
        f'(<i>{webcam["location"]["latitude"]}, {webcam["location"]["longitude"]}</i>)'
    )

    await update.message.reply_photo(
        photo=webcam["images"]["current"]["preview"],
        caption=caption,
        parse_mode=ParseMode.HTML,
    )
