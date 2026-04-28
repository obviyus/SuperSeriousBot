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
    if not message or not message.from_user:
        return

    if context.args:
        query = " ".join(context.args)
    else:
        async with get_db() as conn:
            async with conn.execute(
                "SELECT latitude, longitude FROM weather_cache WHERE user_id = ?",
                (message.from_user.id,),
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            await commands.usage_string(message, weather)
            return
        query = f'{float(row["latitude"])},{float(row["longitude"])}'

    weatherapi_token = config.API.WEATHERAPI_API_KEY
    waqi_token = config.API.WAQI_API_KEY
    if not weatherapi_token or not waqi_token:
        await message.reply_text(
            "Could not fetch weather data. Check WEATHERAPI_API_KEY and WAQI_API_KEY."
        )
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(
            WEATHER_ENDPOINT,
            params={"key": weatherapi_token, "q": query, "aqi": "yes"},
        ) as response:
            raw_weather = await response.json()
        if "error" in raw_weather:
            await message.reply_text(
                "Could not fetch weather data. Check WEATHERAPI_API_KEY and WAQI_API_KEY."
            )
            return

        location = raw_weather["location"]
        current = raw_weather["current"]
        air_quality = current.get("air_quality", {})
        data = {
            "address": ", ".join(
                part
                for part in (location["name"], location["region"], location["country"])
                if part
            ),
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
        async with session.get(
            WAQI_ENDPOINT.format(lat=data["latitude"], lng=data["longitude"]),
            params={"token": waqi_token},
        ) as response:
            raw_aqi = await response.json()
        if raw_aqi.get("status") != "ok":
            await message.reply_text(
                "Could not fetch weather data. Check WEATHERAPI_API_KEY and WAQI_API_KEY."
            )
            return
        aqi_value = raw_aqi["data"].get("aqi")
        data["aqi"] = "Unavailable" if aqi_value is None or aqi_value == "-" else str(int(aqi_value))

    if context.args:
        async with get_db() as conn:
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
                (message.from_user.id, data["latitude"], data["longitude"], data["address"]),
            )

    await message.reply_text(
        f"""<b>{data["address"]}</b>

{data["condition"]}

🌡️ <b>Temperature:</b> {data["temperature"]}
🫠 <b>Feels like:</b> {data["feels_like"]}
💦 <b>Humidity:</b> {data["humidity"]}
💨 <b>Wind:</b> {data["wind"]}
🛰 <b>AQI:</b> {data["aqi"]}
🌫 <b>PM2.5:</b> {data["pm2_5"]}
🏭 <b>PM10:</b> {data["pm10"]}""",
        parse_mode=ParseMode.HTML,
    )



def format_pollutant(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:.1f} µg/m³"

