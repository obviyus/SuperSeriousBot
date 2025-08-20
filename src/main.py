import asyncio
import datetime
import html
import json
import os
import traceback

import caribou
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import commands
from commands.habit import worker_habit_tracker
from commands.highlight import highlight_worker
from commands.remind import worker_reminder
from commands.sed import sed
from config.db import (
    PRIMARY_DB_PATH,
    close_redis,
    get_redis,
    rebuild_fts5,
)
from config.logger import logger
from config.options import config
from management.message_tracking import mention_handler, message_stats_handler
from utils import command_limits


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command handler.
    """
    await update.message.reply_text(f"👋 @{update.effective_user.username}")
    logger.info(f"/start command received from @{update.effective_user.username}")


async def post_init(application: Application) -> None:
    """
    Initialize the bot.
    """
    logger.info(f"Started @{application.bot.username} (ID: {application.bot.id})")

    try:
        redis = await get_redis()
        await redis.set("bot_startup_time", datetime.datetime.now().timestamp())
    except Exception as e:
        logger.error(
            f"Failed to set bot startup time in Redis: {e!s}. Continuing without Redis."
        )

    if (
        "LOGGING_CHANNEL_ID" in config["TELEGRAM"]
        and config["TELEGRAM"]["LOGGING_CHANNEL_ID"]
    ):
        logger.info(
            f"Logging to channel ID: {config['TELEGRAM']['LOGGING_CHANNEL_ID']}"
        )

        await application.bot.send_message(
            chat_id=config["TELEGRAM"]["LOGGING_CHANNEL_ID"],
            text=f"📝 Started @{application.bot.username} (ID: {application.bot.id}) at {datetime.datetime.now()}",
        )

    # Set commands for bot instance
    bot_commands = get_valid_bot_commands(commands.list_of_commands)
    await application.bot.set_my_commands(bot_commands)


async def post_shutdown(application: Application) -> None:
    """
    Shutdown the bot.
    """
    logger.info(f"Shutting down @{application.bot.username} (ID: {application.bot.id})")
    await close_redis()
    logger.info("Cleanup finished.")


def get_valid_bot_commands(command_list: list) -> list[BotCommand]:
    """
    Filter and format valid commands for the bot.
    """
    valid_commands = []
    for command in command_list:
        if hasattr(command, "triggers") and hasattr(command, "description"):
            valid_commands.append(BotCommand(command.triggers[0], command.description))
    return valid_commands


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096-character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)

    # Limit the size of the update dump and traceback to stay under Telegram limits
    try:
        safe_update_json = html.escape(
            json.dumps(update_str, indent=2, ensure_ascii=False)
        )
    except Exception:
        safe_update_json = html.escape(str(update_str))

    safe_update_json = (
        (safe_update_json[:1500] + "…")
        if len(safe_update_json) > 1500
        else safe_update_json
    )
    safe_tb = html.escape("".join(tb_list[-2:]))
    safe_tb = (safe_tb[:1500] + "…") if len(safe_tb) > 1500 else safe_tb

    message = (
        "An exception was raised while handling an update:\n\n"
        f"<pre>update = {safe_update_json}</pre>\n\n"
        f"<pre>{safe_tb}</pre>"
    )

    if (
        "LOGGING_CHANNEL_ID" in config["TELEGRAM"]
        and config["TELEGRAM"]["LOGGING_CHANNEL_ID"]
    ):
        # Finally, send the message
        await context.bot.send_message(
            chat_id=config["TELEGRAM"]["LOGGING_CHANNEL_ID"],
            text=message,
            parse_mode=ParseMode.HTML,
        )


async def setup_application() -> Application:
    await get_redis()

    application = (
        ApplicationBuilder()
        .token(config["TELEGRAM"]["TOKEN"])
        .rate_limiter(AIORateLimiter(max_retries=10))
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_error_handler(error_handler)

    application.add_handlers(
        handlers={
            # Handle reactions to messages
            0: [
                MessageHandler(
                    filters.TEXT,
                    commands.every_message_action,
                ),
            ],
            # Handle commands
            1: commands.command_handler_list,
            # Handle sed and button callbacks
            2: [
                MessageHandler(
                    filters.REPLY & filters.Regex(r"^s\/[\s\S]*\/[\s\S]*"),
                    sed,
                ),
                CallbackQueryHandler(
                    commands.button_handler,
                ),
            ],
            # Handle message stats and mentions
            3: [
                message_stats_handler,
                mention_handler,
            ],
            # Handle highlights
            4: [
                MessageHandler(
                    ~filters.ChatType.PRIVATE,
                    highlight_worker,
                ),
            ],
        }
    )

    job_queue = application.job_queue

    # Notification workers
    job_queue.run_daily(worker_habit_tracker, time=datetime.time(14, 30))
    job_queue.run_repeating(worker_reminder, interval=60, first=10)
    job_queue.run_repeating(rebuild_fts5, interval=3600, first=10)

    # Reset command usage count every day at 12:00 UTC
    job_queue.run_daily(command_limits.reset_command_limits, time=datetime.time(18, 30))

    return application


def main():
    try:
        # AIDEV-NOTE: Migrations are in the project root, not parent directory
        # This works for both Docker (/code/migrations) and local development
        migrations_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "migrations"
        )
        caribou.upgrade(str(PRIMARY_DB_PATH), migrations_dir)
        logger.info(
            f"Running migrations from {migrations_dir} on database {PRIMARY_DB_PATH}"
        )
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Error running database migrations: {e}")

    application = asyncio.get_event_loop().run_until_complete(setup_application())

    if "UPDATER" in config["TELEGRAM"] and config["TELEGRAM"]["UPDATER"] == "webhook":
        logger.info(
            f"Using webhook URL: {config['TELEGRAM']['WEBHOOK_URL']} with port {os.environ.get('PORT', '8443')}"
        )
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", "8443")),
            webhook_url=config["TELEGRAM"]["WEBHOOK_URL"],
        )
    else:
        logger.info("Using polling...")
        application.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
