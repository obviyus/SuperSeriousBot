from __future__ import annotations

import asyncio

import aiohttp
from geopy import Nominatim
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from config.options import config
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message

geolocator = Nominatim(user_agent="SuperSeriousBot")

WAQI_ENDPOINT = "https://api.waqi.info/feed/geo:{lat};{lng}/"


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
            latitude=location.latitude,  # type: ignore
            longitude=location.longitude,  # type: ignore
            address=cls._format_address(location.address),  # type: ignore
        )

    @staticmethod
    def _format_address(address: str) -> str:
        parts = address.split(",")
        try:
            return f"{parts[0].strip()}, {parts[-3].strip()}\n{parts[-1].strip()}, {parts[-2].strip()}"
        except IndexError:
            return address

    async def get_data(self, session: aiohttp.ClientSession) -> dict | None:
        token = config["API"].get("WAQI_API_KEY")
        if not token:
            return None
        url = WAQI_ENDPOINT.format(lat=self.latitude, lng=self.longitude)
        async with session.get(url, params={"token": token}) as response:
            data = await response.json()
            if data.get("status") != "ok":
                return None
            return self._process_waqi_data(data["data"])

    @staticmethod
    def _process_waqi_data(data: dict) -> dict:
        iaqi = data.get("iaqi", {})

        def get_val(key: str) -> str:
            val = iaqi.get(key, {}).get("v")
            return f"{val:.1f}" if val is not None else "N/A"

        aqi = data.get("aqi")
        return {
            "aqi": str(int(aqi)) if aqi and aqi != "-" else "N/A",
            "temperature": f"{get_val('t')} °C",
            "humidity": f"{get_val('h')}%",
            "pressure": f"{get_val('p')} hPa",
            "wind": f"{get_val('w')} m/s",
        }


@usage("/w")
@example("/w")
@triggers(["weather", "w"])
@description("Get the weather for a location. Saves your last location.")
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not message.from_user:
        return

    if not context.args:
        async with get_db() as conn:
            async with conn.execute(
                "SELECT 1 FROM weather_cache WHERE user_id = ?",
                (message.from_user.id,),
            ) as cursor:
                has_cache = await cursor.fetchone() is not None
        if not has_cache:
            await commands.usage_string(message, weather)
            return

    point = await get_point(message.from_user.id, context.args or [])
    if not point.found:
        await message.reply_text("Could not find location.")
        return

    async with aiohttp.ClientSession() as session:
        data = await point.get_data(session)

    if not data:
        await message.reply_text("Could not fetch weather data. Check WAQI_API_KEY.")
        return

    text = format_weather_message(point.address, data)
    await message.reply_text(text, parse_mode=ParseMode.HTML)


async def get_point(user_id: int, args: list[str]) -> Point:
    async with get_db(write=bool(args)) as conn:
        if args:
            point = await Point.from_name(" ".join(args))
            if point.found:
                await conn.execute(
                    """
                    INSERT INTO weather_cache (user_id, latitude, longitude, address, update_time)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        latitude = excluded.latitude,
                        longitude = excluded.longitude,
                        address = excluded.address,
                        update_time = CURRENT_TIMESTAMP
                    """,
                    (user_id, point.latitude, point.longitude, point.address),
                )
        else:
            async with conn.execute(
                "SELECT latitude, longitude, address FROM weather_cache WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                # Should not happen - caller checks cache exists
                point = Point(0.0, 0.0, "")
                point.found = False
                return point
            point = Point(
                float(row["latitude"]),
                float(row["longitude"]),
                row["address"],
            )
    return point


def format_weather_message(address: str, data: dict) -> str:
    return f"""<b>{address}</b>

🌡️ <b>Temperature:</b> {data["temperature"]}
💦 <b>Humidity:</b> {data["humidity"]}
💨 <b>Wind:</b> {data["wind"]}
🛰 <b>AQI:</b> {data["aqi"]}"""
