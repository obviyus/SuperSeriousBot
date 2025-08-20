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

            # Insert message stats
            await conn.execute(
                "INSERT OR IGNORE INTO chat_stats (chat_id, user_id, message_id) VALUES (?, ?, ?)",
                (chat_id, user.id, message.message_id),
            )

            if message.text:
                async with conn.execute(
                    "SELECT fts FROM group_settings WHERE chat_id = ?;",
                    (chat_id,),
                ) as cursor:
                    result = await cursor.fetchone()

                is_enabled = result["fts"] if result else False
                if is_enabled:
                    await conn.execute(
                        "UPDATE chat_stats SET message_text = ? WHERE rowid = last_insert_rowid()",
                        (message.text,),
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


async def handle_message_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle message stats for non-command messages."""
    if not update.message or update.message.text.startswith("/"):
        return

    await _save_message_stats(update.message)


async def handle_mentions(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle mentions in messages."""
    if not update.message or not update.message.from_user:
        return

    mentioning_user_id = update.message.from_user.id

    # Handle text mentions and @ mentions
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == MessageEntity.TEXT_MENTION and entity.user:
                await _save_mention(mentioning_user_id, entity.user.id, update.message)
            elif entity.type == MessageEntity.MENTION:
                mentioned_username = update.message.text[
                    entity.offset + 1 : entity.offset + entity.length
                ]
                async with get_db() as conn:
                    async with conn.execute(
                        "SELECT user_id FROM user_stats WHERE LOWER(username) = ?",
                        (mentioned_username.lower(),),
                    ) as cursor:
                        result = await cursor.fetchone()
                        if result:
                            await _save_mention(
                                mentioning_user_id, result["user_id"], update.message
                            )

    # Handle replies
    elif update.message.reply_to_message and update.message.reply_to_message.from_user:
        await _save_mention(
            mentioning_user_id,
            update.message.reply_to_message.from_user.id,
            update.message,
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
