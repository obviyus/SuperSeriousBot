from telegram import MessageEntity, Update
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
)

from management.chat_memory import process_mentions, save_message_stats
from utils.concurrency import schedule_background_task
from utils.messages import get_message


async def handle_message_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle message stats for non-command messages."""
    message = get_message(update)

    if not message:
        return

    if not message.text or message.text.startswith("/"):
        return

    schedule_background_task(
        save_message_stats(message),
        "message-stats",
    )


async def handle_mentions(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)

    if not message or not message.from_user:
        return

    schedule_background_task(
        process_mentions(message),
        "message-mentions",
    )


message_stats_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_message_stats,
    block=False,
)

mention_handler = MessageHandler(
    filters.TEXT
    & (
        filters.Entity(MessageEntity.MENTION)
        | filters.Entity(MessageEntity.TEXT_MENTION)
        | filters.REPLY
    ),
    handle_mentions,
    block=False,
)
