import os
from dataclasses import asdict, dataclass, field
from typing import Any

from dotenv import load_dotenv

import utils
from config.logger import logger

load_dotenv()

config: dict[str, Any]


@dataclass
class APIConfig:
    COBALT_URL: str = ""
    GIPHY_API_KEY: str = ""
    GOODREADS_API_KEY: str = ""
    NANO_GPT_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    WAQI_API_KEY: str = ""
    WOLFRAM_APP_ID: str = ""


@dataclass
class TelegramConfig:
    TOKEN: str
    QUOTE_CHANNEL_ID: int
    ADMINS: list[str] = field(default_factory=list)
    UPDATER: str = "polling"
    WEBHOOK_URL: str | None = None
    LOGGING_CHANNEL_ID: int | None = None

    def __post_init__(self):
        if self.UPDATER not in ("webhook", "polling"):
            raise ValueError("UPDATER must be 'webhook' or 'polling'")


@dataclass
class Config:
    TELEGRAM: TelegramConfig
    API: APIConfig


try:
    admin_data = [admin for admin in os.environ.get("ADMINS", "").split(" ") if admin]
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN must be set")

    updater = os.environ.get("UPDATER") or "polling"
    webhook_base = os.environ.get("WEBHOOK_URL")
    webhook_url = f"{webhook_base}/{token}" if webhook_base else None

    logging_channel_value = os.environ.get("LOGGING_CHANNEL_ID")
    logging_channel_id = int(logging_channel_value) if logging_channel_value else None

    quote_channel_value = os.environ.get("QUOTE_CHANNEL_ID")
    if not quote_channel_value:
        raise RuntimeError("QUOTE_CHANNEL_ID must be set")
    quote_channel_id = int(quote_channel_value)

    _config_model = Config(
        TELEGRAM=TelegramConfig(
            ADMINS=admin_data,
            TOKEN=token,
            UPDATER=updater,
            WEBHOOK_URL=webhook_url,
            LOGGING_CHANNEL_ID=logging_channel_id,
            QUOTE_CHANNEL_ID=quote_channel_id,
        ),
        API=APIConfig(
            COBALT_URL=os.environ.get("COBALT_URL", ""),
            GIPHY_API_KEY=os.environ.get("GIPHY_API_KEY", ""),
            GOODREADS_API_KEY=os.environ.get("GOODREADS_API_KEY", ""),
            NANO_GPT_API_KEY=os.environ.get("NANO_GPT_API_KEY", ""),
            OPENROUTER_API_KEY=os.environ.get("OPENROUTER_API_KEY", ""),
            WAQI_API_KEY=os.environ.get("WAQI_API_KEY", ""),
            WOLFRAM_APP_ID=os.environ.get("WOLFRAM_APP_ID", ""),
        ),
    )
    logger.info("Valid configuration found.")
    config = utils.scrub_dict(asdict(_config_model))
    logger.info(config)
except ValueError as e:
    logger.error("Invalid configuration found.")
    logger.error(str(e))
    exit(1)
