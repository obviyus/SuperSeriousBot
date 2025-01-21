from dataclasses import dataclass
from datetime import datetime
from typing import Optional

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
CACHE_TIMEOUT = 300  # 5 minutes
REQUEST_TIMEOUT = 10  # seconds


@dataclass
class WebcamData:
    """Container for webcam information"""

    title: str
    status: str
    last_updated: datetime
    city: str
    latitude: float
    longitude: float
    image_url: str

    @classmethod
    def from_api_response(cls, data: dict) -> "WebcamData":
        """Create WebcamData instance from API response"""
        return cls(
            title=data["title"],
            status=data["status"],
            last_updated=dateparser.parse(data["lastUpdatedOn"]),
            city=data["location"]["city"],
            latitude=data["location"]["latitude"],
            longitude=data["location"]["longitude"],
            image_url=data["images"]["current"]["preview"],
        )

    def format_caption(self) -> str:
        """Format webcam information for message caption"""
        minutes_ago = int((datetime.now() - self.last_updated).total_seconds() / 60)
        return (
            f"📹 <b>{self.title}</b> ({self.status})\n\n"
            f"🕒 Last updated: {minutes_ago} minutes ago\n"
            f"📍 {self.city} (<i>{self.latitude}, {self.longitude}</i>)"
        )


async def _get_webcam(latitude: float, longitude: float) -> Optional[WebcamData]:
    """Fetch webcam data from Windy API with caching"""
    params = {
        "nearby": f"{latitude},{longitude},250",
        "include": "location,images",
        "limit": 1,
    }
    headers = {"X-WINDY-API-KEY": config["API"]["WINDY_API_KEY"]}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                WEBCAM_API, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                if not data.get("webcams"):
                    return None

                return WebcamData.from_api_response(data["webcams"][0])

    except (aiohttp.ClientError, KeyError, ValueError):
        return None


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
        await update.message.reply_text("❌ Could not find location.")
        return

    webcam = await _get_webcam(point.latitude, point.longitude)
    if not webcam:
        await update.message.reply_text("❌ No cameras found in this area.")
        return

    try:
        await update.message.reply_photo(
            photo=webcam.image_url,
            caption=webcam.format_caption(),
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        await update.message.reply_text(
            "❌ Failed to fetch camera image. Please try again later."
        )
