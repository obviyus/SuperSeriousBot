import asyncio
import datetime
import html
import json
import os
import traceback
from typing import List

import caribou
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChosenInlineResultHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

import commands
import misc
from commands import steam
from commands.habit import worker_habit_tracker
from commands.randdit import worker_seed_posts
from commands.remind import worker_reminder
from commands.sed import sed
from commands.subscribe import worker_reddit_subscriptions
from commands.tv import handle_chosen_movie, inline_show_search
from commands.youtube import worker_youtube_subscriptions
from config.db import PRIMARY_DB_PATH, initialize_db_pool, rebuild_fts5, redis
from config.logger import logger
from config.options import config
from misc.highlight import highlight_worker
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
    redis.set("bot_startup_time", datetime.datetime.now().timestamp())

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


def get_valid_bot_commands(command_list: List) -> List[BotCommand]:
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
    message = (
        f"An exception was raised while handling an update:\n\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>{html.escape(''.join([tb_list[-1], tb_list[-2]]))}</pre>"
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


def main():
    try:
        migrations_dir = os.path.join(os.getcwd(), "migrations")
        caribou.upgrade(PRIMARY_DB_PATH, migrations_dir)
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Error running database migrations: {e}")

    asyncio.run(initialize_db_pool())

    application = (
        ApplicationBuilder()
        .token(config["TELEGRAM"]["TOKEN"])
        .rate_limiter(AIORateLimiter(max_retries=10))
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    application.add_error_handler(error_handler)

    application.add_handlers(
        handlers={
            # Handle every Update and increment command + message count
            0: [
                MessageHandler(
                    filters.TEXT & filters.Regex(r"^ping$"),
                    commands.ping,
                ),
                MessageHandler(
                    filters.TEXT,
                    commands.every_message_action,
                ),
            ],
            1: commands.command_handler_list,
            2: [
                MessageHandler(
                    filters.REPLY & filters.Regex(r"^s\/[\s\S]*\/[\s\S]*"),
                    sed,
                ),
                # TV Show Query Handlers
                InlineQueryHandler(
                    inline_show_search,
                ),
                # Handle chosen show
                ChosenInlineResultHandler(handle_chosen_movie),
                # Master Button Handler
                CallbackQueryHandler(
                    commands.button_handler,
                ),
            ],
            3: [
                TypeHandler(
                    Update,
                    commands.mention_parser,
                ),
            ],
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
    job_queue.run_repeating(worker_youtube_subscriptions, interval=300, first=10)
    job_queue.run_repeating(worker_reminder, interval=60, first=10)
    job_queue.run_repeating(rebuild_fts5, interval=3600, first=10)

    # Deliver Reddit subscriptions
    job_queue.run_daily(
        worker_reddit_subscriptions,
        time=datetime.time(17, 30),
        job_kwargs={"misfire_grace_time": 60},
    )

    # Reset command usage count every day at 12:00 UTC
    job_queue.run_daily(command_limits.reset_command_limits, time=datetime.time(18, 30))

    # Build social graph
    job_queue.run_daily(misc.worker_build_network, time=datetime.time(19, 30))

    # Seed random Reddit posts
    job_queue.run_once(worker_seed_posts, 10)

    # Steam offer worker
    job_queue.run_repeating(steam.offer_worker, interval=3600, first=10)

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
