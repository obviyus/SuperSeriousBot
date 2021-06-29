import os
from typing import Dict, Union

import yaml

try:
    # By default, try to look for API keys in environment variables
    config: Dict[str, Union[str, list]] = {
        "AUDIO_RESTORE_USERS": os.environ["AUDIO_RESTORE_USERS"].split(),
        "CLIMACELL_API_KEY":   os.environ["CLIMACELL_API_KEY"],
        "FOR_WHAT_ID":         os.environ["FOR_WHAT_ID"],
        "GOODREADS_API_KEY":   os.environ["GOODREADS_API_KEY"],
        "JOGI_FILE_ID":        os.environ["JOGI_FILE_ID"],
        "GIPHY_API_KEY":       os.environ["GIPHY_API_KEY"],
        "PUNYA_SONG_ID":       os.environ["PUNYA_SONG_ID"],
        "SMMRY_API_KEY":       os.environ["SMMRY_API_KEY"],
        "STEAM_API_KEY":       os.environ["STEAM_API_KEY"],
        "TELEGRAM_BOT_TOKEN":  os.environ["TELEGRAM_BOT_TOKEN"],
        "WOLFRAM_APP_ID":      os.environ["WOLFRAM_APP_ID"],
        "AZURE_KEY":           os.environ["AZURE_KEY"],
    }
except KeyError:
    raise ImportError(
        "Cannot import API key. Please check if your environment file is valid."
    )