from __future__ import annotations

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from config.options import config
from utils.decorators import command
from utils.messages import get_message

WEATHER_ENDPOINT = "https://api.weatherapi.com/v1/current.json"
WAQI_ENDPOINT = "https://api.waqi.info/feed/geo:{lat};{lng}/"


@command(
    triggers=["weather", "w"],
    usage="/w",
    example="/w",
    description="Get the weather for a location. Saves your last location.",
)
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not message.from_user:
        return

    query = await get_query(message.from_user.id, context.args or [])
    if query is None:
        await commands.usage_string(message, weather)
        return

    async with aiohttp.ClientSession() as session:
        data = await get_data(session, query)

    if not data:
        await message.reply_text("Could not fetch weather data. Check WEATHERAPI_API_KEY and WAQI_API_KEY.")
        return

    if context.args:
        await save_point(message.from_user.id, data)

    text = format_weather_message(data)
    await message.reply_text(text, parse_mode=ParseMode.HTML)


async def get_query(user_id: int, args: list[str]) -> str | None:
    if args:
        return " ".join(args)
    async with get_db() as conn:
        async with conn.execute(
            "SELECT latitude, longitude FROM weather_cache WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return f'{float(row["latitude"])},{float(row["longitude"])}'


async def get_data(session: aiohttp.ClientSession, query: str) -> dict | None:
    weather = await get_weather_data(session, query)
    if not weather:
        return None
    aqi = await get_aqi_data(session, weather["latitude"], weather["longitude"])
    if not aqi:
        return None
    weather["aqi"] = aqi
    return weather


async def get_weather_data(session: aiohttp.ClientSession, query: str) -> dict | None:
    token = config["API"].get("WEATHERAPI_API_KEY")
    if not token:
        return None
    async with session.get(
        WEATHER_ENDPOINT,
        params={"key": token, "q": query, "aqi": "yes"},
    ) as response:
        data = await response.json()
    if "error" in data:
        return None
    return process_weather_data(data)


def process_weather_data(data: dict) -> dict:
    location = data["location"]
    current = data["current"]
    air_quality = current.get("air_quality", {})
    return {
        "address": format_address(location),
        "latitude": float(location["lat"]),
        "longitude": float(location["lon"]),
        "temperature": f'{current["temp_c"]:.1f} °C',
        "feels_like": f'{current["feelslike_c"]:.1f} °C',
        "condition": current["condition"]["text"],
        "humidity": f'{current["humidity"]}%',
        "wind": f'{current["wind_kph"]:.1f} km/h {current["wind_dir"]}',
        "pm2_5": format_pollutant(air_quality.get("pm2_5")),
        "pm10": format_pollutant(air_quality.get("pm10")),
    }


async def get_aqi_data(
    session: aiohttp.ClientSession,
    latitude: float,
    longitude: float,
) -> str | None:
    token = config["API"].get("WAQI_API_KEY")
    if not token:
        return None
    async with session.get(
        WAQI_ENDPOINT.format(lat=latitude, lng=longitude),
        params={"token": token},
    ) as response:
        data = await response.json()
    if data.get("status") != "ok":
        return None
    return format_aqi(data["data"].get("aqi"))


def format_address(location: dict) -> str:
    parts = [location["name"]]
    if location["region"]:
        parts.append(location["region"])
    parts.append(location["country"])
    return ", ".join(parts)


def format_aqi(value: int | str | None) -> str:
    if value is None or value == "-":
        return "Unavailable"
    return str(int(value))


def format_pollutant(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:.1f} µg/m³"


async def save_point(user_id: int, data: dict) -> None:
    async with get_db(write=True) as conn:
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
            (user_id, data["latitude"], data["longitude"], data["address"]),
        )


def format_weather_message(data: dict) -> str:
    return f"""<b>{data["address"]}</b>

{data["condition"]}

🌡️ <b>Temperature:</b> {data["temperature"]}
🫠 <b>Feels like:</b> {data["feels_like"]}
💦 <b>Humidity:</b> {data["humidity"]}
💨 <b>Wind:</b> {data["wind"]}
🛰 <b>AQI:</b> {data["aqi"]}
🌫 <b>PM2.5:</b> {data["pm2_5"]}
🏭 <b>PM10:</b> {data["pm10"]}"""
