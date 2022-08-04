import httpx
from geopy import Nominatim
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import redis
from utils.decorators import description, example, triggers, usage

geolocator = Nominatim(user_agent="SuperSeriousBot")

WEATHER_ENDPOINT = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


class Point:
    def __init__(self, name, latitude=None, longitude=None, address=None):
        if latitude and longitude and address:
            self.latitude = latitude
            self.longitude = longitude
            self.address = address
            self.found = False
        else:
            location = geolocator.geocode(name, exactly_one=True)
            if not location:
                self.found = False
                return

            self.found = True
            self.latitude = location.latitude
            self.longitude = location.longitude

            try:
                parts = location.address.split(",")
                self.address = f"{parts[0].strip()}, {parts[-3].strip()}\n{parts[-1].strip()}, {parts[-2].strip()}"
            except IndexError:
                self.address = f"{location.address}"

    async def get_weather(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WEATHER_ENDPOINT,
                params={
                    "lat": self.latitude,
                    "lon": self.longitude,
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en-US",
                    "User-Agent": "SuperSeriousBot",
                },
            )

        return response.json()["properties"]["timeseries"][0]["data"]


@triggers(["weather", "w"])
@description("Get the weather for a location. Saves your last location.")
@usage("/w")
@example("/w")
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get the weather for a given location.
    """
    if not context.args and not redis.exists(f"weather:{update.message.from_user.id}"):
        await commands.usage_string(update.message, weather)
        return

    if context.args:
        point = Point(" ".join(context.args))
        if not point.found:
            await update.message.reply_text("Could not find location.")
            return

        point_data = {
            "latitude": point.latitude,
            "longitude": point.longitude,
            "address": point.address,
        }
        redis.hmset(
            f"weather:{update.message.from_user.id}",
            point_data,
        )
    else:
        cached_point = redis.hgetall(f"weather:{update.message.from_user.id}")
        point = Point(
            "",
            float(cached_point["latitude"]),
            float(cached_point["longitude"]),
            cached_point["address"],
        )

    weather_data = await point.get_weather()

    text = f"<b>{point.address}</b>\n\n"
    text += f"""🌡️ <b>Temperature:</b> {weather_data["instant"]["details"]['air_temperature']}°C\n"""
    text += f"""💦 <b>Humidity:</b> {weather_data["instant"]["details"]['relative_humidity']}%\n"""
    text += (
        f"""💨 <b>Wind:</b> {weather_data["instant"]["details"]['wind_speed']} m/s\n\n"""
    )

    text += """🛰️ <b>Forecast:</b>\n"""
    text += f"""<pre>1  hour </pre>: {weather_data["next_1_hours"]["summary"]["symbol_code"]}\n"""
    text += f"""<pre>6  hours</pre>: {weather_data["next_6_hours"]["summary"]["symbol_code"]}\n"""
    text += f"""<pre>12 hours</pre>: {weather_data["next_12_hours"]["summary"]["symbol_code"]}\n"""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
