from datetime import datetime

import httpx
import telegram.error
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from commands.weather import Point
from config import config
from utils.decorators import api_key, description, example, triggers, usage

WEBCAM_API = "https://api.windy.com/api/webcams/v2/list/nearby="


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

    try:
        point = Point(" ".join(context.args))
    except AttributeError:
        await update.message.reply_text(text="Invalid location.")
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(
            WEBCAM_API
            + f"{point.latitude},{point.longitude},radius=250?show=webcams:location,image&limit=1",
            headers={
                "x-windy-key": config["API"]["WINDY_API_KEY"],
            },
        )

    if response.status_code != 200:
        await update.message.reply_text(text="No cameras found.")
        return

    response = response.json()
    if len(response["result"]["webcams"]) == 0:
        await update.message.reply_text(text="No cameras found.")
        return

    webcam = response["result"]["webcams"][0]

    try:
        time_since_update = datetime.now().timestamp() - webcam["image"]["update"]
        await update.message.reply_photo(
            photo=webcam["image"]["current"]["preview"],
            caption=f"""📹 <b>{webcam["title"]}</b> ({webcam["status"]})
            \n🕒 Last updated: {int(time_since_update / 60)} minutes ago
            \n📍 {webcam["location"]["city"]} (<i>{webcam["location"]["latitude"]}, {webcam["location"]["longitude"]}</i>)
            \n🧭 Timezone: {webcam["location"]["timezone"]}""",
            parse_mode=ParseMode.HTML,
        )
    except telegram.error.BadRequest:
        await update.message.reply_text(
            text="Something went wrong while sending the image. Try again later."
        )
        return
