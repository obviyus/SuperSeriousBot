import sqlite3

from typing import Dict, TYPE_CHECKING

from geopy.geocoders import Nominatim
from requests import get

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

weather_codes: Dict[str, str] = {
    "1000": "Clear",
    "1001": "Cloudy",
    "1100": "Mostly Clear",
    "1101": "Partly Cloudy",
    "1102": "Mostly Cloudy",
    "2000": "Fog",
    "2100": "Light Fog",
    "3000": "Light Wind",
    "3001": "Wind",
    "3002": "Strong Wind",
    "4000": "Drizzle",
    "4001": "Rain",
    "4200": "Light Rain",
    "4201": "Heavy Rain",
    "5000": "Snow",
    "5001": "Flurries",
    "5100": "Light Snow",
    "5101": "Heavy Snow",
    "6000": "Freezing Drizzle",
    "6001": "Freezing Rain",
    "6200": "Light Freezing Rain",
    "6201": "Heavy Freezing Rain",
    "7000": "Ice Pellets",
    "7101": "Heavy Ice Pellets",
    "7102": "Light Ice Pellets",
    "8000": "Thunderstorm",
}

conn = sqlite3.connect('/db/stats.db', check_same_thread=False)
cur = conn.cursor()


def weather_details(location):
    weather_data: str
    try:
        params: Dict[str, str] = {
            'location': f'{location.latitude},{location.longitude}',
            'apikey': config["CLIMACELL_API_KEY"],
            'fields': "temperature,humidity,windSpeed,weatherCode,particulateMatter25",
        }

        response = get('https://api.tomorrow.io/v4/timelines?', params=params).json()['data']
        data: Dict = response['timelines'][0]['intervals'][0]['values']

        conditions: str = data['weatherCode']
        humidity: str = data['humidity']
        pm25: str = data['particulateMatter25']
        temperature: str = data['temperature']
        wind_speed: str = data['windSpeed']

        weather_data = f"*{location.address}*\n" \
            f"🌡️ *Temperate:* {temperature}° C\n🏭 *AQI:* {pm25}\n💦 *Humidity:* {humidity}%\n🛰️ *Weather:* {weather_codes[str(conditions)]}\n\n💨 Wind " \
            f"gusts up to *{wind_speed}* m/s "
    except AttributeError:
        weather_data = 'No entry found.'
    return weather_data


def weather(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Show weather at a location"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    user_object = update.message.from_user
    query: str = ' '.join(context.args) if context.args else ''
    text: str

    if not query:
        cur.execute("SELECT location FROM weatherpref WHERE userid = ?", (user_object.id,))
        default_location = cur.fetchone()
        if default_location:
            query = default_location

    if not query:
        text = "*Usage:* `/weather {LOCATION}`\n" \
            "*Example:* `/weather NIT Rourkela` \n" \
            "Or set a default location using `/setw {LOCATION}`"

    else:
        location = Nominatim(user_agent="SuperSeriousBot").geocode(query, exactly_one=True)
        text = weather_details(location)

    message.reply_text(
        text=text,
    )
