import os

from cerberus import Validator

import utils
from config.logger import logger

schema = {
    "TELEGRAM": {
        "type": "dict",
        "schema": {
            "ADMINS": {
                "type": "list",
                "required": False,
                "default": [],
            },
            "TOKEN": {
                "type": "string",
                "required": True,
            },
            "UPDATER": {
                "type": "string",
                "required": False,
                "allowed": ["webhook", "polling"],
                "default": "polling",
            },
            "WEBHOOK_URL": {
                "type": "string",
                "required": False,
            },
            "LOGGING_CHANNEL_ID": {
                "type": "integer",
                "required": False,
                "nullable": True,
            },
        },
    },
    "API": {
        "type": "dict",
        "schema": {
            "GIPHY_API_KEY": {
                "type": "string",
                "required": False,
            },
            "GOODREADS_API_KEY": {
                "type": "string",
                "required": False,
            },
            "SMMRY_API_KEY": {
                "type": "string",
                "required": False,
            },
            "STEAM_API_KEY": {
                "type": "string",
                "required": False,
            },
            "WOLFRAM_APP_ID": {
                "type": "string",
                "required": False,
            },
            "INSTAGRAM_SESSION_NAME": {
                "type": "string",
                "required": False,
            },
            "IMGUR_API_KEY": {
                "type": "string",
                "required": False,
            },
            "YOUTUBE_API_KEY": {
                "type": "string",
                "required": False,
            },
            "REDDIT": {
                "type": "dict",
                "schema": {
                    "CLIENT_ID": {
                        "type": "string",
                        "required": False,
                    },
                    "CLIENT_SECRET": {
                        "type": "string",
                        "required": False,
                    },
                    "USER_AGENT": {
                        "type": "string",
                        "required": False,
                    },
                },
            },
            "TWITTER_BEARER_TOKEN": {
                "type": "string",
                "required": False,
            },
        },
    },
}

config = {
    "TELEGRAM": {
        "ADMINS": os.environ.get("ADMINS", "").split(" "),
        "TOKEN": os.environ.get("TELEGRAM_TOKEN"),
        "UPDATER": os.environ.get("UPDATER"),
        "WEBHOOK_URL": f"""{os.environ.get("WEBHOOK_URL")}/{os.environ.get("TELEGRAM_TOKEN")}""",
        "LOGGING_CHANNEL_ID": int(os.environ.get("LOGGING_CHANNEL_ID"))
        if os.environ.get("LOGGING_CHANNEL_ID")
        else None,
    },
    "API": {
        "GIPHY_API_KEY": os.environ.get("GIPHY_API_KEY", ""),
        "GOODREADS_API_KEY": os.environ.get("GOODREADS_API_KEY", ""),
        "IMGUR_API_KEY": os.environ.get("IMGUR_API_KEY", ""),
        "INSTAGRAM_SESSION_NAME": os.environ.get("INSTAGRAM_SESSION_NAME", ""),
        "REDDIT": {
            "CLIENT_ID": os.environ.get("REDDIT_CLIENT_ID", ""),
            "CLIENT_SECRET": os.environ.get("REDDIT_CLIENT_SECRET", ""),
            "USER_AGENT": os.environ.get("REDDIT_USER_AGENT", ""),
        },
        "SMMRY_API_KEY": os.environ.get("SMMRY_API_KEY", ""),
        "STEAM_API_KEY": os.environ.get("STEAM_API_KEY", ""),
        "TWITTER_BEARER_TOKEN": os.environ.get("TWITTER_BEARER_TOKEN", ""),
        "WOLFRAM_APP_ID": os.environ.get("WOLFRAM_APP_ID", ""),
        "YOUTUBE_API_KEY": os.environ.get("YOUTUBE_API_KEY", ""),
    },
}

v = Validator(schema)
v.allow_unknown = True

if v.validate(config):
    logger.info("Valid configuration found.")
    config = utils.scrub_dict(config)
    logger.info(config)
else:
    logger.error("Invalid configuration found.")
    logger.error(v.errors)
    exit(1)
