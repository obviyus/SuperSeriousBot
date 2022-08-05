import datetime
import html
import json
import os
import traceback

from telegram import MessageEntity, Update
from telegram.constants import ParseMode
from telegram.ext import (
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
from config.db import redis
from config.logger import logger
from config.options import config


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command handler.
    """
    await update.message.reply_text(f"👋 @{update.effective_user.username}")
    logger.info(f"/start command received from @{update.effective_user.username}")


async def post_init(application: Application) -> None:
    """
    Initialise the bot.
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
    await application.bot.set_my_commands(
        [
            (command.triggers[0], command.description)
            for command in commands.list_of_commands
        ]
    )


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
    application = (
        ApplicationBuilder()
        .token(config["TELEGRAM"]["TOKEN"])
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    application.add_error_handler(error_handler)
    job_queue = application.job_queue

    application.add_handlers(
        handlers={
            # Handle every Update and increment command + message count
            0: [
                TypeHandler(
                    Update,
                    commands.increment_command_count,
                )
            ],
            1: [
                MessageHandler(
                    filters.REPLY & filters.Regex(r"^s\/[\s\S]*\/[\s\S]*"),
                    commands.sed,
                ),
                MessageHandler(
                    filters.TEXT & filters.Regex(r"^ping$"),
                    commands.ping,
                ),
                # Filter for all URLs
                MessageHandler(
                    filters.Entity(MessageEntity.URL)
                    | filters.Entity(MessageEntity.TEXT_LINK),
                    misc.twitter_preview,
                ),
                # TV Show Query Handlers
                InlineQueryHandler(
                    commands.inline_show_search,
                ),
                ChosenInlineResultHandler(
                    commands.inline_result_handler,
                ),
                # Master Button Handler
                CallbackQueryHandler(
                    commands.button_handler,
                ),
            ],
            2: commands.command_handler_list,
        }
    )

    # TV Show notification workers
    job_queue.run_daily(commands.worker_next_episode, time=datetime.time(0, 0))
    job_queue.run_repeating(commands.worker_episode_notifier, interval=300, first=10)

    # Deliver Reddit subscriptions
    job_queue.run_daily(
        commands.worker_reddit_subscriptions, time=datetime.time(17, 30)
    )

    # Seed random Reddit posts
    job_queue.run_once(commands.worker_seed_posts, 10)
    job_queue.run_once(commands.worker_image_seeder, 10)

    if "UPDATER" in config["TELEGRAM"] and config["TELEGRAM"]["UPDATER"] == "webhook":
        logger.info(f"Using webhook URL: {config['TELEGRAM']['WEBHOOK_URL']}")
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", "8443")),
            url_path=config["TELEGRAM"]["TOKEN"],
            webhook_url=config["TELEGRAM"]["WEBHOOK_URL"],
        )
    else:
        logger.info(f"Using polling...")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
