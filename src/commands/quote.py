import enum

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
import utils
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


class FileType(enum.Enum):
    """File type enum."""

    DOCUMENT = "DOCUMENT"
    PHOTO = "PHOTO"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    ANIMATION = "ANIMATION"
    VOICE = "VOICE"
    STICKER = "STICKER"
    UNKNOWN = "UNKNOWN"


@usage("/addquote")
@example("/addquote")
@triggers(["addquote"])
@description("Reply to a message to save it into QuotesDB.")
async def add_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save chat message to QoutesDB."""
    if not update.message.reply_to_message:
        await commands.usage_string(update.message, add_quote)
        return

    if update.message.has_protected_content:
        await update.message.reply_text(
            "This is protected and cannot be forwarded.",
        )
        return

    quote_message = update.message.reply_to_message

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM quote_db WHERE message_id = ?;
        """,
        (quote_message.message_id,),
    )

    if cursor.fetchone():
        await update.message.reply_text(
            f"This message has already been saved.",
            parse_mode=ParseMode.HTML,
        )
        return

    cursor.execute(
        """
        INSERT INTO quote_db (message_id, chat_id, message_user_id, saver_user_id) VALUES (?, ?, ?, ?);
        """,
        (
            quote_message.message_id,
            quote_message.chat_id,
            quote_message.from_user.id,
            update.message.from_user.id,
        ),
    )

    await update.message.reply_text(
        f"Quote added by @{await utils.get_username(update.message.from_user.id, context)}.",
        parse_mode=ParseMode.HTML,
    )


@usage("/quote, /q")
@example("/quote, /q")
@triggers(["quote", "q"])
@description("Return a random message from QuotesDB for this group.")
async def get_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a quote from QuotesDB."""
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM quote_db WHERE chat_id = ? ORDER BY RANDOM() LIMIT 1;
        """,
        (update.message.chat_id,),
    )

    row = cursor.fetchone()
    if not row:
        await update.message.reply_text(
            f"No quotes found in this chat.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.chat.forward_from(row["chat_id"], row["message_id"])
