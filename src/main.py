import contextlib
import datetime
import html
import json
import os
import re
import traceback

import caribou
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
from commands.habit import worker_habit_tracker
from commands.highlight import highlight_worker
from commands.remind import worker_reminder
from commands.sed import sed
from config.db import (
    PRIMARY_DB_PATH,
    close_db,
    init_db,
    optimize_fts5,
)
from config.logger import logger
from config.options import config
from management.message_tracking import mention_handler, message_stats_handler
from utils import command_limits
from utils.decorators import get_command_meta

bot_startup_time: float | None = None


def ensure_caribou_py314_compat() -> None:
    """
    Adjust Caribou's SQLite parameter handling for Python 3.14.
    """
    from caribou import migrate as caribou_migrate

    if getattr(caribou_migrate, "_py314_param_patch", False):
        return

    placeholder_pattern = re.compile(r":([0-9]+)")
    original_transaction = caribou_migrate.transaction

    @contextlib.contextmanager
    def patched_execute(conn, sql, params=None):
        params = [] if params is None else params
        if isinstance(params, (list, tuple)):
            placeholders = placeholder_pattern.findall(sql)
            if placeholders:
                params = {
                    name: params[idx]
                    for idx, name in enumerate(placeholders)
                    if idx < len(params)
                }
        cursor = conn.execute(sql, params)
        try:
            yield cursor
        finally:
            cursor.close()

    def patched_update_version(self, version):
        sql = f"update {caribou_migrate.VERSION_TABLE} set version = ?"
        with original_transaction(self.conn):
            self.conn.execute(sql, (version,))

    setattr(caribou_migrate, "execute", patched_execute)  # noqa: B010
    setattr(caribou_migrate.Database, "update_version", patched_update_version)  # noqa: B010
    setattr(caribou_migrate, "_py314_param_patch", True)  # noqa: B010


async def post_init(application: Application) -> None:
    """
    Initialize the bot.
    """
    global bot_startup_time
    await init_db()
    logger.info(f"Started @{application.bot.username} (ID: {application.bot.id})")

    bot_startup_time = datetime.datetime.now().timestamp()

    logging_channel_id = config["TELEGRAM"].get("LOGGING_CHANNEL_ID")
    if logging_channel_id:
        logger.info(
            f"Logging to channel ID: {logging_channel_id}"
        )

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


async def post_shutdown(application: Application) -> None:
    """
    Shutdown the bot.
    """
    logger.info(f"Shutting down @{application.bot.username} (ID: {application.bot.id})")
    await close_db()
    logger.info("Cleanup finished.")



async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Skip transient network errors (ConnectError, timeouts) - these are normal and auto-retried
    if isinstance(context.error, NetworkError) and "ConnectError" in str(context.error):
        logger.debug("Transient network error (ConnectError), skipping: %s", context.error)
        return

    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__ if context.error else None
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

    logging_channel_id = config["TELEGRAM"].get("LOGGING_CHANNEL_ID")
    if logging_channel_id:
        # Finally, send the message
        await context.bot.send_message(
            chat_id=logging_channel_id,
            text=message,
            parse_mode=ParseMode.HTML,
        )


def main():
    ensure_caribou_py314_compat()
    migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
    logger.info(f"Running migrations from {migrations_dir} on database {PRIMARY_DB_PATH}")
    try:
        caribou.upgrade(str(PRIMARY_DB_PATH), migrations_dir)
    except Exception:
        logger.exception("Error running database migrations")
        raise
    logger.info("Database migrations completed successfully.")
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
        }
    )
    job_queue = application.job_queue
    if job_queue is None:
        raise RuntimeError(
            "Job queue not initialized. Install python-telegram-bot[job-queue]."
        )
    job_queue.run_daily(worker_habit_tracker, time=datetime.time(14, 30))
    job_queue.run_repeating(worker_reminder, interval=60, first=10)
    job_queue.run_repeating(optimize_fts5, interval=21600, first=60)
    job_queue.run_daily(command_limits.reset_command_limits, time=datetime.time(18, 30))
    if config["TELEGRAM"]["UPDATER"] == "polling":
        logger.info("Using polling...")
        application.run_polling(drop_pending_updates=False)
        return

    webhook_url = config["TELEGRAM"]["WEBHOOK_URL"]
    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL must be set when UPDATER is 'webhook'")
    port = int(os.environ.get("PORT", "8443"))
    logger.info(f"Using webhook URL: {webhook_url} with port {port}")
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()
