import asyncio
import time

import dateparser
import httpx
from geopy import Nominatim
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import redis
from utils.decorators import description, example, triggers, usage

geolocator = Nominatim(user_agent="SuperSeriousBot")

WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
AQI_ENDPOINT = "https://air-quality-api.open-meteo.com/v1/air-quality"


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
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "hourly": "temperature_2m,apparent_temperature,windspeed_10m,relativehumidity_1000hPa",
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en-US",
                    "User-Agent": "SuperSeriousBot",
                },
            )

        # Find index in the time series that is closest to BEFORE the current time
        current_time, current_time_index = time.time(), 0
        parsed_response = response.json()

        for index, data in enumerate(parsed_response["hourly"]["time"]):
            parsed_time = dateparser.parse(data)
            if parsed_time.timestamp() > current_time:
                current_time_index = index - 1 if index > 0 else 0
                break

        return {
            "temperature": f"""{parsed_response["hourly"]["temperature_2m"][
                current_time_index
            ]} {parsed_response["hourly_units"]["temperature_2m"]}""",
            "apparent_temperature": f"""{parsed_response["hourly"]["apparent_temperature"][
                current_time_index
            ]} {parsed_response["hourly_units"]["apparent_temperature"]}""",
            "windspeed": f"""{parsed_response["hourly"]["windspeed_10m"][
                current_time_index
            ]} {parsed_response["hourly_units"]["windspeed_10m"]}""",
            "relative_humidity": f"""{parsed_response["hourly"]["relativehumidity_1000hPa"][
                current_time_index
            ]} {parsed_response["hourly_units"]["relativehumidity_1000hPa"]}""",
        }

    async def get_pm25(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                AQI_ENDPOINT,
                params={
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "hourly": "pm2_5",
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en-US",
                    "User-Agent": "SuperSeriousBot",
                },
            )

            # Find index in the time series that is closest to BEFORE the current time
            current_time, current_time_index = time.time(), 0
            parsed_response = response.json()

            for index, data in enumerate(parsed_response["hourly"]["time"]):
                parsed_time = dateparser.parse(data)
                if parsed_time.timestamp() > current_time:
                    current_time_index = index - 1 if index > 0 else 0
                    break

            return f"""{parsed_response["hourly"]["pm2_5"][current_time_index]} {parsed_response["hourly_units"]["pm2_5"]}"""


@usage("/w")
@example("/w")
@triggers(["weather", "w"])
@description("Get the weather for a location. Saves your last location.")
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

    # Await both together
    weather_data, aqi = await asyncio.gather(point.get_weather(), point.get_pm25())

    text = f"<b>{point.address}</b>\n\n"
    text += f"""🌡️ <b>Temperature:</b> {weather_data["temperature"]}\n"""
    text += f"""☁️️ <b>Feels like:</b> {weather_data["apparent_temperature"]}\n"""
    text += f"""💦 <b>Humidity:</b> {weather_data["relative_humidity"]}\n"""
    text += f"""💨 <b>Wind:</b> {weather_data["windspeed"]}\n"""
    text += f"""🛰 <b>AQI:</b> {aqi}\n\n"""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
