import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

import utils
from config.logger import logger

load_dotenv()


class APIConfig(BaseModel):
    GIPHY_API_KEY: str | None = ""
    GOODREADS_API_KEY: str | None = ""
    SMMRY_API_KEY: str | None = ""
    STEAM_API_KEY: str | None = ""
    WOLFRAM_APP_ID: str | None = ""
    INSTAGRAM_SESSION_NAME: str | None = ""
    IMGUR_API_KEY: str | None = ""
    OPEN_AI_API_KEY: str | None = ""
    YOUTUBE_API_KEY: str | None = ""
    RAPID_API_KEY: str | None = ""
    WINDY_API_KEY: str | None = ""
    NANO_GPT_API_KEY: str | None = ""
    EMBEDEZ_API_KEY: str | None = ""
    OPENROUTER_API_KEY: str | None = ""
    GOOGLE_API_KEY: str | None = ""
    COBALT_URL: str | None = ""


class TelegramConfig(BaseModel):
    ADMINS: list[str] = Field(default_factory=list)
    TOKEN: str
    UPDATER: str | None = Field(default="polling", pattern="^(webhook|polling)$")
    WEBHOOK_URL: str | None = None
    LOGGING_CHANNEL_ID: int | None = None
    QUOTE_CHANNEL_ID: int


class Config(BaseModel):
    TELEGRAM: TelegramConfig
    API: APIConfig


try:
    config = Config(
        TELEGRAM={
            "ADMINS": os.environ.get("ADMINS", "").split(" "),
            "TOKEN": os.environ.get("TELEGRAM_TOKEN"),
            "UPDATER": os.environ.get("UPDATER"),
            "WEBHOOK_URL": f"""{os.environ.get("WEBHOOK_URL")}/{os.environ.get("TELEGRAM_TOKEN")}""",
            "LOGGING_CHANNEL_ID": (
                int(os.environ.get("LOGGING_CHANNEL_ID"))
                if os.environ.get("LOGGING_CHANNEL_ID")
                else None
            ),
            "QUOTE_CHANNEL_ID": int(os.environ.get("QUOTE_CHANNEL_ID")),
        },
        API={
            "GIPHY_API_KEY": os.environ.get("GIPHY_API_KEY", ""),
            "GOODREADS_API_KEY": os.environ.get("GOODREADS_API_KEY", ""),
            "IMGUR_API_KEY": os.environ.get("IMGUR_API_KEY", ""),
            "INSTAGRAM_SESSION_NAME": os.environ.get("INSTAGRAM_SESSION_NAME", ""),
            "RAPID_API_KEY": os.environ.get("RAPID_API_KEY", ""),
            "SMMRY_API_KEY": os.environ.get("SMMRY_API_KEY", ""),
            "STEAM_API_KEY": os.environ.get("STEAM_API_KEY", ""),
            "OPEN_AI_API_KEY": os.environ.get("OPEN_AI_API_KEY", ""),
            "WOLFRAM_APP_ID": os.environ.get("WOLFRAM_APP_ID", ""),
            "WINDY_API_KEY": os.environ.get("WINDY_API_KEY", ""),
            "YOUTUBE_API_KEY": os.environ.get("YOUTUBE_API_KEY", ""),
            "NANO_GPT_API_KEY": os.environ.get("NANO_GPT_API_KEY", ""),
            "EMBEDEZ_API_KEY": os.environ.get("EMBEDEZ_API_KEY", ""),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
            "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
            "COBALT_URL": os.environ.get("COBALT_URL", ""),
        },
    )
    logger.info("Valid configuration found.")
    config_dict = utils.scrub_dict(config.model_dump())
    config = config_dict
    logger.info(config_dict)
except ValidationError as e:
    logger.error("Invalid configuration found.")
    logger.error(e.json())
    exit(1)
