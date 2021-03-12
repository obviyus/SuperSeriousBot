import datetime
from typing import TYPE_CHECKING, Dict
from urllib.parse import urlencode

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


def weather(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Show weather at a location"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    query: str = ' '.join(context.args) if context.args else ''
    parse_mode: str = 'Markdown'
    text: str

    if not query:
        text = "*Usage:* `/weather {LOCATION}`\n" \
               "*Example:* `/weather NIT Rourkela`"
    else:
        geolocator: Nominatim = Nominatim(user_agent="SuperSeriousBot")
        location = geolocator.geocode(query)

        try:
            payload: Dict[str, str] = {
                'location': f'{location.latitude},{location.longitude}',
                'apikey': config["CLIMACELL_API_KEY"],  # type: ignore
                'fields': "cloudCover,temperature,humidity,"
                          "windSpeed,weatherCode",
                'startTime': datetime.datetime.now().replace(microsecond=0).isoformat() + 'Z',
                'endTime': (datetime.datetime.now() + datetime.timedelta(hours=1)).replace(
                    microsecond=0).isoformat() + 'Z'
            }

            response = get('https://data.climacell.co/v4/timelines?' + urlencode(payload))

            if response.status_code == 200:
                data: Dict = response.json()['data']
                current: Dict = data['timelines'][0]['intervals'][0]['values']

                temperature: str = current['temperature']
                cloud_cover: str = current['cloudCover']
                humidity: str = current['humidity']
                wind_speed: str = current['windSpeed']
                conditions: str = current['weatherCode']

                text = f"<b>{location.address}</b>\n" \
                       f"<b>🌡️ Temperate</b>: {temperature}° C\n<b>☁ Cloud Cover</b>: {cloud_cover}%\n<b>💦 " \
                       f"Humidity</b>: {humidity}%\n<b>🛰️ Weather</b>: {weather_codes[str(conditions)]}\n\n💨 Wind " \
                       f"gusts up to {wind_speed} m/s "
                parse_mode = 'HTML'

                message.reply_text(
                    text=text,
                    parse_mode=parse_mode
                )
                return
            else:
                text = 'No entry found.'
        except AttributeError:
            text = 'No entry found.'

    message.reply_text(
        text=text,
        parse_mode=parse_mode
    )
