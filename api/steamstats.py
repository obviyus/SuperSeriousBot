import sqlite3
import time
from datetime import datetime
from typing import TYPE_CHECKING, Dict

import dateutil.relativedelta
import requests

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect('/db/steam_id.db', check_same_thread=False)
cursor = conn.cursor()

formula: str = f"CREATE TABLE IF NOT EXISTS `telegram_steam_id` ( " \
               "`telegram_id` VARCHAR(255) NOT NULL UNIQUE, " \
               "`steam_id` VARCHAR(255) NOT NULL, " \
               "PRIMARY KEY (`telegram_id`))"
cursor.execute(formula)

STEAM_API_KEY = config["STEAM_API_KEY"]

profile_states = {
    0: 'Offline',
    1: 'Online',
    2: 'Busy',
    3: 'Away',
    4: 'Snooze',
    5: 'Looking to trade',
    6: 'Looking to play'
}


def is_public_profile(steam_id: str) -> bool:
    url: str = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    params: Dict[str, str] = {"key": STEAM_API_KEY, "steamids": steam_id}

    try:
        response = requests.get(url, params).json()
        return response["response"]["players"][0]["communityvisibilitystate"] == 3
    except KeyError:
        return False


def player_summary(steam_id: str) -> str:
    url: str = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    params: Dict[str, str] = {"key": STEAM_API_KEY, "steamids": steam_id}

    text: str
    try:
        response = requests.get(url, params).json()["response"]["players"][0]
        last_online: str = datetime.utcfromtimestamp(response["lastlogoff"]).strftime("%B %d, %Y")
        profile_age = dateutil.relativedelta.relativedelta(datetime.now(),
                                                           datetime.fromtimestamp(response["timecreated"]))
        text = f"""Current Status: {profile_states[response["profilestate"]]}\nLast Online: {last_online}\nProfile Age: {profile_age.years} years"""

        return text
    except KeyError:
        return ""


def last_played(steam_id: str) -> str:
    url: str = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"
    params: Dict[str, str] = {"key": STEAM_API_KEY, "steamid": steam_id}

    text: str
    try:
        response = requests.get(url, params).json()["response"]
        game_count = response["total_count"]

        hours_2weeks = sum(game["playtime_2weeks"] for game in response["games"])
        text = f"""Last 2 Weeks: {game_count} games played with {hours_2weeks // 60} hours"""

        return text
    except KeyError:
        return ""


def hours_and_games(username: str, steam_id: str) -> (str, int):
    url: str = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params: Dict[str, str] = {"key": STEAM_API_KEY, "steamid": steam_id, "include_appinfo": "true", "format": "json",
                              "include_played_free_games": "true"}

    try:
        response: Dict[str, Dict] = requests.get(url, params).json()
        username: str = username.replace('_', '\_')

        response = response["response"]
        games_owned = response["game_count"]

        total_time: int = sum(game["playtime_forever"] for game in response["games"])
        sorted_games = sorted(response["games"], key=lambda x: x["playtime_forever"], reverse=True)

        total_hours = total_time // 60

        text = f"@{username}'s Steam Stats:" \
               f"\n\n**Games Owned**: {games_owned}\n**Total Playtime**: {total_hours} hours " \
               f"\n\n{last_played(steam_id)}" \
               f"""\n\n**Most Played Games**:"""

        top_3_sum = 0
        for i in range(3):
            text += f"""  \n{i + 1}. {sorted_games[i]["name"]} - {sorted_games[i]["playtime_forever"] // 60} hours"""
            top_3_sum += sorted_games[i]["playtime_forever"]

        text += f"\n\nThese games contributed to **{round((top_3_sum / total_time) * 100, 1)}%** of the total playtime"

        return text, total_hours

    except KeyError:
        return "Cannot read stats for private Steam profiles.", -1


def make_steam_response(username: str, steam_id: str) -> (str, int):
    text: str

    text, hours = hours_and_games(username, steam_id)
    if hours != -1:
        text += "\n\n" + player_summary(steam_id)

    return text, hours


def steamstats(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Print Steam stats for a user"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    hours: int = -1
    steam_id: str
    telegram_user_id: int = message.from_user.id

    cursor.execute(f"SELECT * FROM telegram_steam_id WHERE telegram_id={telegram_user_id}")
    result = cursor.fetchall()

    if len(result) == 0:
        text = "No SteamID is set. Use /setid to set one."
    else:
        steam_id = result[0][1]
        if is_public_profile(steam_id):
            text, hours = make_steam_response(message.from_user.username, steam_id)
        else:
            text = "Cannot read stats for private Steam profiles."

    message.reply_text(
        text=text,
        parse_mode='Markdown'
    )

    if hours > 5000:
        time.sleep(2)
        message.reply_text("Holy shit go outside")
