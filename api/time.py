from requests import get
from datetime import datetime
from configuration import config


def time(update, context):
    """Command to tell time at a place."""
    message = update.message
    place = ' '.join(context.args)

    if not place:
        text = "*Usage:* `/time {PLACE}`\n"\
               "*Example:* `/time katowice`"\
               "Add the data code for the specific country for better results."
    else:
        key = config["OPENWEATHER_API_KEY"]
        response = get(
            f"http://api.openweathermap.org/data/2.5/weather?id=524901&APPID={key}&q={place}"
        )

        if response.ok:
            data = response.json()
            timezone = data['timezone']
            current_unix_time = datetime.utcnow().timestamp() + timezone

            full_time = (
                datetime.fromtimestamp(int(current_unix_time)).strftime("%I:%M %p|%d-%m-%Y")
            )
            time, date = full_time.split('|')

            text = f"*{time}*\n_{date}_"
        else:
            text = "No entry found."

    context.bot.send_message(chat_id=message.chat_id, text=text)
