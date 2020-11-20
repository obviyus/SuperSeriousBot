import yaml
import os


try:
    # By default, try to look for API keys in environment variables
    data = {}
    data["TELEGRAM_BOT_TOKEN"] = os.environ["TELEGRAM_BOT_TOKEN"]
    data["WOLFRAM_APP_ID"] = os.environ["WOLFRAM_APP_ID"]
    data["OPENWEATHER_API_KEY"] = os.environ["OPENWEATHER_API_KEY"]
    data["GOODREADS_API_KEY"] = os.environ["GOODREADS_API_KEY"]
    data["AIRVISUAL_API_KEY"] = os.environ["AIRVISUAL_API_KEY"]
    data["JOGI_FILE_ID"] = os.environ["JOGI_FILE_ID"]
    data["FOR_WHAT_ID"] = os.environ["FOR_WHAT_ID"]
    data["PUNYA_SONG_ID"] = os.environ["PUNYA_SONG_ID"]
except KeyError:
    try:
        with open("config.yaml", 'r') as config:
            data = yaml.safe_load(config)
            config = data
    except FileNotFoundError:
        raise FileNotFoundError(
            "\nPlease create a 'config.yaml' file and put the credentials needed for the bot in it.\n"
            "Refer configuration/example_config.yaml for a template"
        )
