import asyncio
import time

import aiohttp
from geopy import Nominatim
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_redis
from utils.decorators import description, example, triggers, usage

geolocator = Nominatim(user_agent="SuperSeriousBot")

WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
AQI_ENDPOINT = "https://air-quality-api.open-meteo.com/v1/air-quality"


class Point:
    def __init__(
        self,
        latitude: float,
        longitude: float,
        address: str,
    ):
        self.found = True
        self.latitude = latitude
        self.longitude = longitude
        self.address = address

    @classmethod
    async def from_name(cls, name: str) -> Point:
        location = await asyncio.to_thread(geolocator.geocode, name, exactly_one=True)
        if not location:
            p = cls(0.0, 0.0, "")
            p.found = False
            return p
        return cls(
            latitude=location.latitude,
            longitude=location.longitude,
            address=cls._format_address(location.address),
        )

    @staticmethod
    def _format_address(address: str) -> str:
        parts = address.split(",")
        try:
            return f"{parts[0].strip()}, {parts[-3].strip()}\n{parts[-1].strip()}, {parts[-2].strip()}"
        except IndexError:
            return address

    async def get_data(self, session: aiohttp.ClientSession) -> tuple[dict, str]:
        weather_data, aqi = await asyncio.gather(
            self._fetch_weather(session), self._fetch_aqi(session)
        )
        return weather_data, aqi

    async def _fetch_weather(self, session: aiohttp.ClientSession) -> dict:
        async with session.get(
            WEATHER_ENDPOINT,
            params={
                "latitude": self.latitude,
                "longitude": self.longitude,
                "hourly": "temperature_2m,apparent_temperature,windspeed_10m,relativehumidity_1000hPa",
            },
        ) as response:
            data = await response.json()
            return self._process_weather_data(data)

    async def _fetch_aqi(self, session: aiohttp.ClientSession) -> str:
        async with session.get(
            AQI_ENDPOINT,
            params={
                "latitude": self.latitude,
                "longitude": self.longitude,
                "hourly": "pm2_5",
            },
        ) as response:
            data = await response.json()
            return self._process_aqi_data(data)

    @staticmethod
    def _process_weather_data(data: dict) -> dict:
        current_index = Point._get_current_time_index(data["hourly"]["time"])
        return {
            "temperature": f"{data['hourly']['temperature_2m'][current_index]} {data['hourly_units']['temperature_2m']}",
            "apparent_temperature": f"{data['hourly']['apparent_temperature'][current_index]} {data['hourly_units']['apparent_temperature']}",
            "windspeed": f"{data['hourly']['windspeed_10m'][current_index]} {data['hourly_units']['windspeed_10m']}",
            "relative_humidity": f"{data['hourly']['relativehumidity_1000hPa'][current_index]} {data['hourly_units']['relativehumidity_1000hPa']}",
        }

    @staticmethod
    def _process_aqi_data(data: dict) -> str:
        current_index = Point._get_current_time_index(data["hourly"]["time"])
        return (
            f"{data['hourly']['pm2_5'][current_index]} {data['hourly_units']['pm2_5']}"
        )

    @staticmethod
    def _get_current_time_index(time_series: list[str]) -> int:
        """Return the index of the most recent time <= now using binary search.

        Compares ISO-8601 timestamps as strings at minute precision, avoiding
        heavy parsing. Assumes ascending order.
        """
        if not time_series:
            return 0

        # Current UTC time formatted to match series precision
        target = time.strftime("%Y-%m-%dT%H:%M", time.gmtime())

        def norm(ts: str) -> str:
            # Normalize to 'YYYY-MM-DDTHH:MM', drop trailing 'Z' if present
            if ts.endswith("Z"):
                ts = ts[:-1]
            return ts[:16]

        lo, hi = 0, len(time_series) - 1
        ans = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if norm(time_series[mid]) <= target:
                ans = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return ans


@usage("/w")
@example("/w")
@triggers(["weather", "w"])
@description("Get the weather for a location. Saves your last location.")
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    redis = await get_redis()
    if not context.args and not await redis.exists(
        f"weather:{update.message.from_user.id}"
    ):
        await commands.usage_string(update.message, weather)
        return

    point = await get_point(update.message.from_user.id, context.args)
    if not point.found:
        await update.message.reply_text("Could not find location.")
        return

    async with aiohttp.ClientSession() as session:
        weather_data, aqi = await point.get_data(session)

    text = format_weather_message(point.address, weather_data, aqi)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def get_point(user_id: int, args: list) -> Point:
    redis = await get_redis()
    if args:
        point = await Point.from_name(" ".join(args))
        if point.found:
            await redis.hset(
                f"weather:{user_id}",
                mapping={
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "address": point.address,
                },
            )
    else:
        cached_point = await redis.hgetall(f"weather:{user_id}")
        point = Point(
            float(cached_point["latitude"]),
            float(cached_point["longitude"]),
            cached_point["address"],
        )
    return point


def format_weather_message(address: str, weather_data: dict, aqi: str) -> str:
    return f"""<b>{address}</b>

🌡️ <b>Temperature:</b> {weather_data["temperature"]}
☁️️ <b>Feels like:</b> {weather_data["apparent_temperature"]}
💦 <b>Humidity:</b> {weather_data["relative_humidity"]}
💨 <b>Wind:</b> {weather_data["windspeed"]}
🛰 <b>AQI:</b> {aqi}"""
