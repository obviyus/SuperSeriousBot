import yaml
import os

try:
    # By default, try to look for API keys in environment variables
    config = {"TELEGRAM_BOT_TOKEN": os.environ["TELEGRAM_BOT_TOKEN"],
              "MYSQL_USER": os.environ["MYSQL_USER"],
              "MYSQL_IP_ALIAS": os.environ["MYSQL_IP_ALIAS"],
              "MYSQL_PASSWORD": os.environ["MYSQL_PASSWORD"],
              "CLOUDMERSIVE_API_KEY": os.environ["CLOUDMERSIVE_API_KEY"],
              "WOLFRAM_APP_ID": os.environ["WOLFRAM_APP_ID"],
              "GIPHY_API_KEY": os.environ["GIPHY_API_KEY"],
              "OPENWEATHER_API_KEY": os.environ["OPENWEATHER_API_KEY"],
              "GOODREADS_API_KEY": os.environ["GOODREADS_API_KEY"],
              "CLIMACELL_API_KEY": os.environ["CLIMACELL_API_KEY"],
              "JOGI_FILE_ID": os.environ["JOGI_FILE_ID"],
              "FOR_WHAT_ID": os.environ["FOR_WHAT_ID"],
              "PUNYA_SONG_ID": os.environ["PUNYA_SONG_ID"],
              "AUDIO_RESTORE_USERS": os.environ["AUDIO_RESTORE_USERS"].split()}
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
