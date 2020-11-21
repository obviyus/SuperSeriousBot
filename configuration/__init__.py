import yaml
import os

try:
    # By default, try to look for API keys in environment variables
    config = {"TELEGRAM_BOT_TOKEN": os.environ["TELEGRAM_BOT_TOKEN"],
              "MYSQL_USERNAME": os.environ["MYSQL_USERNAME"],
              "MYSQL_PW": os.environ["MYSQL_PW"],
              "WOLFRAM_APP_ID": os.environ["WOLFRAM_APP_ID"],
              "OPENWEATHER_API_KEY": os.environ["OPENWEATHER_API_KEY"],
              "GOODREADS_API_KEY": os.environ["GOODREADS_API_KEY"],
              "AIRVISUAL_API_KEY": os.environ["AIRVISUAL_API_KEY"],
              "JOGI_FILE_ID": os.environ["JOGI_FILE_ID"],
              "FOR_WHAT_ID": os.environ["FOR_WHAT_ID"],
              "PUNYA_SONG_ID": os.environ["PUNYA_SONG_ID"],
              "FILE_RESTORE_USERS": os.environ["FILE_RESTORE_USERS"].split()}
except KeyError:
    try:
        with open("config.yaml", 'r') as config:
            config = yaml.safe_load(config)
    except FileNotFoundError:
        raise FileNotFoundError(
            "\nPlease create a 'config.yaml' file and put the credentials needed for the bot in it.\n"
            "Refer configuration/example_config.yaml for a template.\n"
            "You can alternatively set environmental variables."
        )
