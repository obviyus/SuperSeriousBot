import sqlite3
from geopy.geocoders import Nominatim
from .weather import weather_details

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect('/db/stats.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS weatherpref
               (userid int PRIMARY KEY, location text)''')


def setw(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Set default location for weather."""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    user_object = update.message.from_user
    result: str
    query: str = ' '.join(context.args) if context.args else ''

    if not query:
        result = "*Usage:* `/setw {LOCATION}`\n" \
            "*Example:* `/setw NIT Rourkela`"
    else:
        try:
            location = Nominatim(user_agent="dumbfuckingbot").geocode(query, exactly_one=True)
            if location is None:
                raise TypeError
        except TypeError:
            result = "No entry found."
        else:
            cur.execute("INSERT INTO weatherpref(userid,location) VALUES(?,?) \
                ON CONFLICT(userid) DO UPDATE SET location=excluded.location", (user_object.id, query))
            conn.commit()
            result = f"Default location has been set. \n" \
                f" \n{ weather_details(location) }"

    message.reply_text(text=result)
