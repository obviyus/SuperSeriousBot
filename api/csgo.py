import sqlite3
from json.decoder import JSONDecodeError
from typing import TYPE_CHECKING, Dict, List

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


def make_csgo_response(username: str, steam_id: str) -> str:
    url: str = "https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/"
    params: Dict[str, str] = {"appid": "730", "key": STEAM_API_KEY, "steamid": steam_id}

    try:
        response: Dict[str, Dict] = requests.get(url, params).json()
        username: str = username.replace('_', '\_')

        best_map: Dict[str, str] = {"value": "0"}
        sanitized_dict: Dict[str, int] = dict()
        for each_stat in response["playerstats"]["stats"]:
            sanitized_dict[each_stat["name"]] = each_stat["value"]
            if "map" in each_stat["name"]:
                if int(each_stat["value"]) > int(best_map["value"]):
                    best_map = each_stat

        total_time_played: int = sanitized_dict["total_time_played"]
        total_kills: float = float(sanitized_dict["total_kills"])
        total_deaths: float = float(sanitized_dict["total_deaths"])
        total_knife_kills: int = sanitized_dict["total_kills_knife"]
        total_headshot_kills: int = sanitized_dict["total_kills_headshot"]
        kdr: float = round(total_kills / total_deaths, 2)
        total_wins: int = sanitized_dict["total_wins"]

        gun_kills: List[Dict[str, str]] = response["playerstats"]["stats"][10:23]
        gun_kills.sort(key=lambda element: element["value"])

        best_map_name = '_'.join(best_map["name"].split('_')[3:])

        text: str = f"**CSGO Stats for @{username}:**" \
                    f"\n\nTotal Kills: {int(total_kills)}" \
                    f"\nHeadshot Kills: {total_headshot_kills}" \
                    f"\nKnife Kills: {total_knife_kills}" \
                    f"\nTotal Deaths: {int(total_deaths)}" \
                    f"\nKDR: {kdr}" \
                    f"\n\n**Top 3 guns:**"

        for i in range(3):
            current_gun = gun_kills.pop(-1)
            name = current_gun["name"].split('_')[-1].upper()
            text += f"""\n{i + 1}. {name} - {current_gun["value"]} kills"""

        text += f"""\n\nBest Map: `{best_map_name}` with {best_map["value"]} wins""" \
                f"\n\nTotal Wins: {total_wins}" \
                f"\nTotal Time Played: {round(total_time_played / 3600)} hours"
    except JSONDecodeError:
        text = "Cannot read stats for private Steam profiles."

    return text


def set_steam_id(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Set your SteamID"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    username: str = ' '.join(context.args).strip() if context.args else ''
    text: str

    if not username:
        text = "*Usage:* `/setid {STEAM_ACCOUNT_NAME}`\n" \
               "*Example:* `/setid obviyus`\n" \
               "This is not your steam username, but your steam account name."
    elif ' ' in username:
        text = "This command does not work with Steam usernames."
    elif len(username) == 17 and username.isdigit():
        try:
            url: str = "https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/"
            params: Dict[str, str] = {"appid": "730", "key": STEAM_API_KEY, "steamid": username}
            response: Dict[str, Dict] = requests.get(url, params).json()

            _ = response["playerstats"]["stats"]
            telegram_user_id: int = message.from_user.id

            insert_formula = f"INSERT INTO `telegram_steam_id` (telegram_id, steam_id) " \
                             f"VALUES ('{telegram_user_id}', '{username}')" \
                             f"ON CONFLICT(telegram_id) DO UPDATE SET steam_id = {username}"

            cursor.execute(insert_formula)
            text = f"SteamID successfully set to {username}"
        except JSONDecodeError:
            text = "Profile is private or does not exist."
    else:
        steam_id: str
        telegram_user_id: int = message.from_user.id

        url: str = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001"
        params: Dict[str, str] = {"key": STEAM_API_KEY, "vanityurl": username}

        try:
            response: Dict[str, Dict] = requests.get(url, params).json()

            try:
                steam_id = response["response"]["steamid"]

                insert_formula = f"INSERT INTO `telegram_steam_id` (telegram_id, steam_id) " \
                                 f"VALUES ('{telegram_user_id}', '{steam_id}')" \
                                 f"ON CONFLICT(telegram_id) DO UPDATE SET steam_id = {steam_id}"

                cursor.execute(insert_formula)
                text = f"SteamID successfully set to {steam_id}"
            except KeyError:
                text = f"Cannot find SteamID for {username}"
        except JSONDecodeError:
            text = "Cannot read stats for private Steam profiles."

    conn.commit()
    message.reply_text(
        text=text
    )


def csgo(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Print CSGO stats for a user"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    steam_id: str
    telegram_user_id: int = message.from_user.id

    cursor.execute(f"SELECT * FROM telegram_steam_id WHERE telegram_id={telegram_user_id}")
    result = cursor.fetchall()

    if len(result) == 0:
        text = "No SteamID is set. Use /setid to set one."
    else:
        steam_id = result[0][1]
        text = make_csgo_response(message.from_user.username, steam_id)

    message.reply_text(
        text=text
    )
