import os
from typing import Dict, Union

config: Dict[str, Union[str, list]] = {
    "DEV_USERNAMES": os.getenv("DEV_USERNAMES", "").split(),
    "CLIMACELL_API_KEY": os.getenv("CLIMACELL_API_KEY", ""),
    "FOR_WHAT_ID": os.getenv("FOR_WHAT_ID", ""),
    "GOODREADS_API_KEY": os.getenv("GOODREADS_API_KEY", ""),
    "JOGI_FILE_ID": os.getenv("JOGI_FILE_ID", ""),
    "GIPHY_API_KEY": os.getenv("GIPHY_API_KEY", ""),
    "PUNYA_SONG_ID": os.getenv("PUNYA_SONG_ID", ""),
    "SMMRY_API_KEY": os.getenv("SMMRY_API_KEY", ""),
    "STEAM_API_KEY": os.getenv("STEAM_API_KEY", ""),
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "WOLFRAM_APP_ID": os.getenv("WOLFRAM_APP_ID", ""),
    "AZURE_KEY": os.getenv("AZURE_KEY", ""),
    "IMGUR_KEY": os.getenv("IMGUR_KEY", ""),
    "PYTHON_QBITTORRENTAPI_HOST": os.getenv("PYTHON_QBITTORRENTAPI_HOST", ""),
    "PYTHON_QBITTORRENTAPI_USERNAME": os.getenv("PYTHON_QBITTORRENTAPI_USERNAME", ""),
    "PYTHON_QBITTORRENTAPI_PASSWORD": os.getenv("PYTHON_QBITTORRENTAPI_PASSWORD", ""),
    "REDDIT_CLIENT_ID": os.getenv("REDDIT_CLIENT_ID", ""),
    "REDDIT_CLIENT_SECRET": os.getenv("REDDIT_CLIENT_SECRET", ""),
    "REDDIT_USER_AGENT": os.getenv("REDDIT_USER_AGENT", ""),
    "TESTING": os.getenv("TESTING", ""),
}

if config["TELEGRAM_BOT_TOKEN"] == "":
    raise Exception("Telegram Bot Token not provided, bot cannot run without it")
