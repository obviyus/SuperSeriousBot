import os
from typing import Dict, Union

import yaml

try:
    # By default, try to look for API keys in environment variables
    config: Dict[str, Union[str, list]] = {
        "TELEGRAM_BOT_TOKEN": os.environ["TELEGRAM_BOT_TOKEN"],
        "AUDIO_RESTORE_USERS": os.environ["AUDIO_RESTORE_USERS"].split(),
        "CLIMACELL_API_KEY": os.environ["CLIMACELL_API_KEY"],
        "CLOUDMERSIVE_API_KEY": os.environ["CLOUDMERSIVE_API_KEY"],
        "FOR_WHAT_ID": os.environ["FOR_WHAT_ID"],
        "GOODREADS_API_KEY": os.environ["GOODREADS_API_KEY"],
        "JOGI_FILE_ID": os.environ["JOGI_FILE_ID"],
        "OPENWEATHER_API_KEY": os.environ["OPENWEATHER_API_KEY"],
        "PUNYA_SONG_ID": os.environ["PUNYA_SONG_ID"],
        "STEAM_API_KEY": os.environ["STEAM_API_KEY"],
        "WOLFRAM_APP_ID": os.environ["WOLFRAM_APP_ID"],
    }
except KeyError:
    try:
        with open("config.yaml", 'r') as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(
            "\nPlease create a 'config.yaml' file and put the credentials needed for the bot in it.\n"
            "Refer configuration/example_config.yaml for a template.\n"
            "You can alternatively set environmental variables."
        )
