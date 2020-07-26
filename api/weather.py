from geopy.geocoders import Nominatim
from requests import get
from configuration import config


def weather(update, context):
    message = update.message
    query = ' '.join(context.args)
    parse_mode = 'Markdown'

    if not query:
        text = "*Usage:* `/aqi {LOCATION}`\n"\
               "*Example:* `/aqi NIT Rourkela`"

    else:
        geolocator = Nominatim(user_agent="SuperSeriousBot")
        location = geolocator.geocode(query)

        try:
            response = get(f'http://api.airvisual.com/v2/nearest_city?lat={location.latitude}&lon={location.longitude}&key={config["AIRVISUAL_API_KEY"]}')
            response = response.json()

            if response['status'] == "success":
                data = response['data']
                current = data['current']

                aqi_us = current['pollution']['aqius']
                tp = current['weather']['tp']
                pressure = current['weather']['pr']
                humidity = current['weather']['hu']
                wind_speed = current['weather']['ws']

                text = f"<b>{data['city']}, {data['country']}</b>\n"\
                    f"<b>🎐 AQI</b>: {aqi_us}\n"\
                    f"<b>🌡️ Temperate</b>: {tp}° C\n<b>📊 Pressure</b>: {pressure} hPa\n<b>💦 Humidity</b>: {humidity}%\n\n💨 Wind gusts up to {wind_speed} m/s"
                parse_mode = 'HTML'
            else:
                text = 'No entry found.'
        except AttributeError:
            text = 'No entry found.'

    message.reply_text(
        text=text,
        parse_mode=parse_mode
    )
