import datetime
import html
import json
import os
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ChosenInlineResultHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

import commands
import management
from config.logger import logger
from config.options import config
from db import redis


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command handler.
    """
    await context.bot.wrong_method_name()  # type: ignore[attr-defined]
    # await update.message.reply_text(f"👋 @{update.effective_user.username}")
    logger.info(f"/start command received from @{update.effective_user.username}")


async def post_init(application: Application) -> None:
    """
    Initialise the bot.
    """
    bot = await application.bot.get_me()
    logger.info(f"Started @{bot.username} (ID: {bot.id})")
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
            text=f"📝 Started @{bot.username} (ID: {bot.id}) at {datetime.datetime.now()}",
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
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
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


async def disabled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Disabled command handler.
    """
    await update.message.reply_text("❌ This command is disabled.")


command_list = [
    CommandHandler("start", start),
    CommandHandler("stats", management.get_chat_stats),
    CommandHandler("botstats", management.get_command_stats),
    CommandHandler("seen", management.get_last_seen),
    CommandHandler("dl", commands.downloader),
    CommandHandler(
        "c", commands.get_top_comment if "REDDIT" in config["API"] else disabled
    ),
]


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
            -1: command_list,
            1: [
                MessageHandler(
                    filters.REPLY & filters.Regex(r"^s\/[\s\S]*\/[\s\S]*"), commands.sed
                ),
                MessageHandler(filters.TEXT & filters.Regex(r"^ping$"), commands.ping),
                InlineQueryHandler(commands.inline_show_search),
                ChosenInlineResultHandler(commands.inline_result_handler),
            ],
            # Handle every Update and increment command + message count
            2: [TypeHandler(Update, management.increment_command_count)],
        }
    )

    # TV Show notification workers
    job_queue.run_daily(commands.worker_next_episode, time=datetime.time(0, 0))
    job_queue.run_repeating(commands.worker_episode_notifier, interval=300, first=10)

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
        application.run_polling()


if __name__ == "__main__":
    main()
