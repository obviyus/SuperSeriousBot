import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from config.logger import logger

load_dotenv()


@dataclass
class APIConfig:
    COBALT_URL: str = ""
    GIPHY_API_KEY: str = ""
    GOODREADS_API_KEY: str = ""
    NANO_GPT_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    WAQI_API_KEY: str = ""
    WEATHERAPI_API_KEY: str = ""
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
    admin_data = os.environ.get("ADMINS", "").split()
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN must be set")

    updater = os.environ.get("UPDATER") or "polling"
    webhook_base = os.environ.get("WEBHOOK_URL")
    webhook_url = f"{webhook_base}/{token}" if webhook_base else None
    logging_channel_id = (
        int(value) if (value := os.environ.get("LOGGING_CHANNEL_ID")) else None
    )

    quote_channel_value = os.environ.get("QUOTE_CHANNEL_ID")
    if not quote_channel_value:
        raise RuntimeError("QUOTE_CHANNEL_ID must be set")

    _config_model = Config(
        TELEGRAM=TelegramConfig(
            ADMINS=admin_data,
            TOKEN=token,
            UPDATER=updater,
            WEBHOOK_URL=webhook_url,
            LOGGING_CHANNEL_ID=logging_channel_id,
            QUOTE_CHANNEL_ID=int(quote_channel_value),
        ),
        API=APIConfig(
            **{name: os.environ.get(name, "") for name in APIConfig.__annotations__}
        ),
    )
    logger.info("Valid configuration found.")
    config = _config_model
    logger.info(
        "Config summary: updater=%s admins=%d quote_channel_id=%s logging_channel=%s",
        config.TELEGRAM.UPDATER,
        len(config.TELEGRAM.ADMINS),
        bool(config.TELEGRAM.QUOTE_CHANNEL_ID),
        bool(config.TELEGRAM.LOGGING_CHANNEL_ID),
    )
except ValueError as e:
    logger.error("Invalid configuration found.")
    logger.error(str(e))
    exit(1)
