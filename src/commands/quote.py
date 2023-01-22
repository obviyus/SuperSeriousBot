from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import commands
import utils
from config import config
from config.db import sqlite_conn
from utils.decorators import api_key, description, example, triggers, usage


@api_key("QUOTE_CHANNEL_ID")
@description("Reply to a message to save it into QuotesDB.")
@example("/addquote")
@triggers(["addquote"])
@usage("/addquote")
async def add_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save chat message to QuotesDB."""
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

    # Forward message to Quotes Channel
    try:
        forwarded_message = await quote_message.forward(
            chat_id=config["TELEGRAM"]["QUOTE_CHANNEL_ID"],
        )
    except BadRequest:
        await update.message.reply_text(
            "This message cannot be stored.",
        )
        return

    cursor.execute(
        """
        INSERT INTO quote_db (message_id, chat_id, message_user_id, saver_user_id, forwarded_message_id) VALUES (?, ?, ?, ?, ?);
        """,
        (
            quote_message.message_id,
            quote_message.chat_id,
            quote_message.from_user.id,
            update.message.from_user.id,
            forwarded_message.message_id,
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

    try:
        await update.message.chat.forward_from(
            config["TELEGRAM"]["QUOTE_CHANNEL_ID"], row["forwarded_message_id"]
        )
    except BadRequest:
        await update.message.reply_text(
            f"Quoted message deleted. Removing the quote.",
            parse_mode=ParseMode.HTML,
        )
        cursor.execute(
            """
            DELETE FROM quote_db WHERE id = ?;
            """,
            (row["id"],),
        )


async def migrate_quote_db(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Migrate old QuoteDB to quote channel."""
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM quote_db WHERE forwarded_message_id IS NULL;
        """,
    )

    row = cursor.fetchall()
    if not row:
        return

    for quote in row:
        try:
            message = await context.bot.forward_message(
                chat_id=config["TELEGRAM"]["QUOTE_CHANNEL_ID"],
                from_chat_id=quote["chat_id"],
                message_id=quote["message_id"],
            )
        except BadRequest:
            cursor.execute(
                """
                DELETE FROM quote_db WHERE id = ?;
                """,
                (quote["id"],),
            )
            continue

        cursor.execute(
            """
            UPDATE quote_db SET forwarded_message_id = ? WHERE id = ?;
            """,
            (message.message_id, quote["id"]),
        )
