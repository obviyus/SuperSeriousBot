import datetime
import math
from urllib.parse import urlencode

from geopy.geocoders import Nominatim
from requests import get

from configuration import config


def coords_to_tile(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


weather_codes = {
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


def weather(update, context):
    """Show weather at a location"""
    message = update.message
    query = ' '.join(context.args)
    parse_mode = 'Markdown'

    if not query:
        text = "*Usage:* `/weather {LOCATION}`\n" \
               "*Example:* `/weather NIT Rourkela`"

    else:
        geolocator = Nominatim(user_agent="SuperSeriousBot")
        location = geolocator.geocode(query)

        try:
            time_now = datetime.datetime.now()
            payload = {
                'location': f'{location.latitude},{location.longitude}',
                'apikey': config["CLIMACELL_API_KEY"],
                'fields': "cloudCover,temperature,humidity,"
                          "windSpeed,weatherCode",
                'startTime': time_now.replace(microsecond=0).isoformat() + 'Z',
                'endTime': (time_now + datetime.timedelta(hours=1)).replace(
                    microsecond=0).isoformat() + 'Z'
            }

            response = get('https://data.climacell.co/v4/timelines?' +
                           urlencode(payload))

            if response.status_code == 200:
                data = response.json()['data']
                current = data['timelines'][0]['intervals'][0]['values']

                temperature = current['temperature']
                cloud_cover = current['cloudCover']
                humidity = current['humidity']
                wind_speed = current['windSpeed']
                conditions = current['weatherCode']

                text = f"<b>{location.address}</b>\n" \
                       f"<b>🌡️ Temperate</b>: {temperature}° C\n<b>☁ Cloud Cover</b>: {cloud_cover}%\n<b>💦 " \
                       f"Humidity</b>: {humidity}%\n<b>🛰️ Weather</b>: {weather_codes[str(conditions)]}\n\n💨 Wind " \
                       f"gusts up to {wind_speed} m/s "
                parse_mode = 'HTML'

                zoom = 5
                x, y = coords_to_tile(location.latitude, location.longitude, zoom)
                map = f'https://data.climacell.co/v4/map/tile/{zoom}/{x}/{y}/humidity?apikey={config["CLIMACELL_API_KEY"]}'

                message.reply_photo(
                    photo=map,
                    caption=text,
                    parse_mode=parse_mode
                )
                return
            else:
                text = f'{response}'
        except AttributeError as e:
            text = f'{e}'

    message.reply_text(
        text=text,
        parse_mode=parse_mode
    )
