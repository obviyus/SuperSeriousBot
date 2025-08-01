import os
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

from config.logger import logger
from dotenv import load_dotenv

import utils

load_dotenv()


class APIConfig(BaseModel):
    GIPHY_API_KEY: Optional[str] = ""
    GOODREADS_API_KEY: Optional[str] = ""
    SMMRY_API_KEY: Optional[str] = ""
    STEAM_API_KEY: Optional[str] = ""
    WOLFRAM_APP_ID: Optional[str] = ""
    INSTAGRAM_SESSION_NAME: Optional[str] = ""
    IMGUR_API_KEY: Optional[str] = ""
    OPEN_AI_API_KEY: Optional[str] = ""
    YOUTUBE_API_KEY: Optional[str] = ""
    RAPID_API_KEY: Optional[str] = ""
    WINDY_API_KEY: Optional[str] = ""
    NANO_GPT_API_KEY: Optional[str] = ""
    EMBEDEZ_API_KEY: Optional[str] = ""
    OPENROUTER_API_KEY: Optional[str] = ""
    GOOGLE_API_KEY: Optional[str] = ""


class TelegramConfig(BaseModel):
    ADMINS: List[str] = Field(default_factory=list)
    TOKEN: str
    UPDATER: Optional[str] = Field(default="polling", pattern="^(webhook|polling)$")
    WEBHOOK_URL: Optional[str] = None
    LOGGING_CHANNEL_ID: Optional[int] = None
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
