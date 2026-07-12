import datetime
import html
import json
import os
import traceback

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.error import NetworkError
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
from commands.cron_service import register_enabled_cron_tasks
from commands.football import sync_football_fixtures_job, worker_football_alerts
from commands.habit import worker_habit_tracker
from commands.highlight import highlight_worker
from commands.remind import worker_reminder
from commands.sed import sed
from config.db import (
    close_db,
    init_db,
)
from config.logger import logger
from config.options import config
from management.chat_search_index import index_pending_windows, indexed_chat_ids
from management.message_tracking import mention_handler, message_stats_handler
from utils import command_limits
from utils.decorators import get_command_meta

bot_startup_time: float | None = None


async def post_init(application: Application) -> None:
    """
    Initialize the bot.
    """
    global bot_startup_time
    await init_db()
    logger.info(f"Started @{application.bot.username} (ID: {application.bot.id})")

    bot_startup_time = datetime.datetime.now().timestamp()

    logging_channel_id = config.TELEGRAM.LOGGING_CHANNEL_ID
    if logging_channel_id:
        logger.info(f"Logging to channel ID: {logging_channel_id}")

        await application.bot.send_message(
            chat_id=logging_channel_id,
            text=f"📝 Started @{application.bot.username} (ID: {application.bot.id}) at {datetime.datetime.now()}",
        )

    await application.bot.set_my_commands(
        [
            BotCommand(meta.triggers[0], meta.description)
            for bot_command in commands.list_of_commands
            if (meta := get_command_meta(bot_command))
            and meta.triggers
            and meta.description
            and commands.is_command_enabled(bot_command)
        ]
    )

    await register_enabled_cron_tasks(application.job_queue)


async def post_shutdown(application: Application) -> None:
    """
    Shutdown the bot.
    """
    logger.info(f"Shutting down @{application.bot.username} (ID: {application.bot.id})")
    await close_db()
    logger.info("Cleanup finished.")


async def worker_chat_search_index(_: ContextTypes.DEFAULT_TYPE) -> None:
    indexed = await index_pending_windows(
        config.API.OPENROUTER_API_KEY,
        chat_ids=await indexed_chat_ids(),
    )
    if indexed:
        logger.info("Indexed %d chat search windows", indexed)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    if isinstance(context.error, NetworkError) and "ConnectError" in str(context.error):
        logger.debug(
            "Transient network error (ConnectError), skipping: %s", context.error
        )
        return

    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__ if context.error else None
    )
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    safe_update_json = html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))
    if len(safe_update_json) > 1500:
        safe_update_json = safe_update_json[:1500] + "…"
    safe_tb = html.escape("".join(tb_list[-2:]))
    if len(safe_tb) > 1500:
        safe_tb = safe_tb[:1500] + "…"

    message = (
        "An exception was raised while handling an update:\n\n"
        f"<pre>update = {safe_update_json}</pre>\n\n"
        f"<pre>{safe_tb}</pre>"
    )

    logging_channel_id = config.TELEGRAM.LOGGING_CHANNEL_ID
    if logging_channel_id:
        await context.bot.send_message(
            chat_id=logging_channel_id,
            text=message,
            parse_mode=ParseMode.HTML,
        )


def main():
    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM.TOKEN)
        .rate_limiter(AIORateLimiter(max_retries=10))
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_error_handler(error_handler)
    application.add_handlers(
        handlers={
            0: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    commands.every_message_action,
                )
            ],
            1: commands.command_handler_list,
            2: [
                MessageHandler(
                    filters.REPLY & filters.Regex(r"^s\/[\s\S]*\/[\s\S]*"), sed
                ),
                CallbackQueryHandler(commands.button_handler),
            ],
            3: [message_stats_handler, mention_handler],
            4: [MessageHandler(~filters.ChatType.PRIVATE, highlight_worker)],
            5: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE,
                    commands.auto_dl_message_handler,
                )
            ],
        }
    )
    job_queue = application.job_queue
    if job_queue is None:
        raise RuntimeError(
            "Job queue not initialized. Install python-telegram-bot[job-queue]."
        )
    job_queue.run_daily(worker_habit_tracker, time=datetime.time(14, 30))
    job_queue.run_once(
        sync_football_fixtures_job,
        when=5,
        name="sync_football_fixtures_startup",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    job_queue.run_daily(
        sync_football_fixtures_job,
        time=datetime.time(3, tzinfo=datetime.UTC),
        name="sync_football_fixtures_daily",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    job_queue.run_repeating(
        worker_football_alerts,
        interval=60,
        first=15,
        name="worker_football_alerts",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    job_queue.run_repeating(
        worker_reminder,
        interval=60,
        first=10,
        name="worker_reminder",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    search_index_enabled = bool(config.API.OPENROUTER_API_KEY)
    if search_index_enabled:
        job_queue.run_repeating(
            worker_chat_search_index,
            interval=900,
            first=30,
            name="worker_chat_search_index",
            job_kwargs={"max_instances": 1, "coalesce": True},
        )
    job_queue.run_daily(command_limits.reset_command_limits, time=datetime.time(18, 30))
    if config.TELEGRAM.UPDATER == "polling":
        logger.info("Using polling...")
        application.run_polling(drop_pending_updates=False)
        return

    webhook_url = config.TELEGRAM.WEBHOOK_URL
    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL must be set when UPDATER is 'webhook'")
    port = int(os.environ.get("PORT", "8443"))
    # WEBHOOK_URL embeds the bot token as the path — never log it.
    logger.info("Using webhook mode on port %s", port)
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()
