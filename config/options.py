import os
from urllib.parse import urljoin

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
            "AZURE_API_KEY": {
                "type": "string",
                "required": False,
            },
            "CLIMACELL_API_KEY": {
                "type": "string",
                "required": False,
            },
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
            "WOLFRAM_API_KEY": {
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
        },
    },
}

config = {
    "TELEGRAM": {
        "ADMINS": os.environ.get("ADMINS", "").split(" "),
        "TOKEN": os.environ.get("TELEGRAM_TOKEN"),
        "UPDATER": os.environ.get("UPDATER"),
        "WEBHOOK_URL": urljoin(
            os.environ.get("WEBHOOK_URL"), os.environ.get("TELEGRAM_TOKEN")
        ),
        "LOGGING_CHANNEL_ID": int(os.environ.get("LOGGING_CHANNEL_ID"))
        if os.environ.get("LOGGING_CHANNEL_ID")
        else None,
    },
    "API": {
        "AZURE_API_KEY": os.environ.get("AZURE_API_KEY", ""),
        "CLIMACELL_API_KEY": os.environ.get("CLIMACELL_API_KEY", ""),
        "GIPHY_API_KEY": os.environ.get("GIPHY_API_KEY", ""),
        "GOODREADS_API_KEY": os.environ.get("GOODREADS_API_KEY", ""),
        "SMMRY_API_KEY": os.environ.get("SMMRY_API_KEY", ""),
        "WOLFRAM_API_KEY": os.environ.get("WOLFRAM_API_KEY", ""),
        "IMGUR_API_KEY": os.environ.get("IMGUR_API_KEY", ""),
        "YOUTUBE_API_KEY": os.environ.get("YOUTUBE_API_KEY", ""),
        "REDDIT": {
            "CLIENT_ID": os.environ.get("REDDIT_CLIENT_ID", ""),
            "CLIENT_SECRET": os.environ.get("REDDIT_CLIENT_SECRET", ""),
            "USER_AGENT": os.environ.get("REDDIT_USER_AGENT", ""),
        },
    },
}

v = Validator(schema)
v.allow_unknown = True

if v.validate(config):
    logger.info("Valid configuration found.")
    config = utils.scrub_dict(config)
else:
    logger.error("Invalid configuration found.")
    logger.error(v.errors)
    exit(1)
