"""
Message tracking and stats handlers.
"""

from datetime import datetime

from telegram import Message, MessageEntity, Update
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
)

from config.db import get_db
from utils.concurrency import schedule_background_task
from utils.messages import get_message


async def _save_message_stats(message: Message) -> None:
    """Save message stats to database."""
    if not message.from_user or not message.from_user.username:
        return

    user = message.from_user
    chat_id = message.chat_id

    async with get_db(write=True) as conn:
        try:
            # Update user stats
            await conn.execute(
                """
                INSERT INTO user_stats (user_id, username, last_seen, last_message_link)
                    VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    last_seen = excluded.last_seen,
                    last_message_link = excluded.last_message_link
                """,
                (
                    user.id,
                    user.username,
                    datetime.now(),
                    message.link if message.link else None,
                ),
            )

            # Check if FTS is enabled for this chat
            # AIDEV-NOTE: We include message_text in the INSERT (not a separate UPDATE)
            # so the chat_stats_ai trigger fires with the actual text, making it
            # immediately searchable without needing periodic FTS rebuilds.
            message_text = None
            if message.text:
                async with conn.execute(
                    "SELECT fts FROM group_settings WHERE chat_id = ?;",
                    (chat_id,),
                ) as cursor:
                    result = await cursor.fetchone()
                if result and result["fts"]:
                    message_text = message.text

            # Insert message stats with text if FTS enabled
            await conn.execute(
                """
                INSERT OR IGNORE INTO chat_stats (chat_id, user_id, message_id, message_text)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, user.id, message.message_id, message_text),
            )

            await conn.commit()
        except Exception as e:
            await conn.rollback()
            print(f"Error in save_message_stats: {e}")


async def _save_mention(
    mentioning_user_id: int,
    mentioned_user_id: int,
    message: Message,
) -> None:
    """Save mention data to database."""
    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO chat_mentions (mentioning_user_id, mentioned_user_id, chat_id, message_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                mentioning_user_id,
                mentioned_user_id,
                message.chat.id,
                message.message_id,
            ),
        )
        await conn.commit()


async def _get_user_id_by_username(username: str) -> int | None:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT user_id FROM user_stats WHERE LOWER(username) = ?",
            (username.lower(),),
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return result["user_id"]
    return None


async def handle_message_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle message stats for non-command messages."""
    message = get_message(update)

    if not message:
        return

    if not message.text or message.text.startswith("/"):
        return

    schedule_background_task(
        _save_message_stats(message),
        "message-stats",
    )


async def _process_mentions(message: Message) -> None:
    if not message.from_user:
        return

    mentioning_user_id = message.from_user.id
    # AIDEV-NOTE: Track mentioned users to avoid duplicates within same message
    mentioned_users: set[int] = set()

    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntity.TEXT_MENTION and entity.user:
                if entity.user.id not in mentioned_users:
                    mentioned_users.add(entity.user.id)
                    await _save_mention(mentioning_user_id, entity.user.id, message)
            elif entity.type == MessageEntity.MENTION and message.text:
                mentioned_username = message.text[
                    entity.offset + 1 : entity.offset + entity.length
                ]
                user_id = await _get_user_id_by_username(mentioned_username)
                if user_id is not None and user_id not in mentioned_users:
                    mentioned_users.add(user_id)
                    await _save_mention(mentioning_user_id, user_id, message)

    # Also track replies as mentions (don't return early after entities)
    if message.reply_to_message and message.reply_to_message.from_user:
        replied_user_id = message.reply_to_message.from_user.id
        if replied_user_id not in mentioned_users:
            await _save_mention(mentioning_user_id, replied_user_id, message)


async def handle_mentions(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle mentions in messages."""
    message = get_message(update)

    if not message or not message.from_user:
        return

    schedule_background_task(
        _process_mentions(message),
        "message-mentions",
    )


# Create handlers with appropriate priorities
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
