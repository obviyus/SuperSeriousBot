from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import commands
import utils
from config import config
from config.db import get_db
from utils.decorators import api_key, description, example, triggers, usage
from utils.messages import get_message


@api_key("QUOTE_CHANNEL_ID")
@description("Reply to a message to save it into QuotesDB.")
@example("/addquote")
@triggers(["addquote"])
@usage("/addquote")
async def add_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return
    """Save chat message to QuotesDB."""
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await commands.usage_string(message, add_quote) if message else None
        return

    if message.has_protected_content:
        await message.reply_text(
            "This is protected and cannot be forwarded.",
        )
        return

    quote_message = message.reply_to_message
    # quote_message.from_user is guaranteed to be non-None due to check on line 26
    assert quote_message.from_user is not None

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM quote_db WHERE message_id = ?;
            """,
            (quote_message.message_id,),
        ) as cursor:
            if await cursor.fetchone():
                await message.reply_text(
                    "This message has already been saved.",
                    parse_mode=ParseMode.HTML,
                )
                return

    try:
        forwarded_message = await quote_message.forward(
            chat_id=config["TELEGRAM"]["QUOTE_CHANNEL_ID"],
        )
    except BadRequest:
        await message.reply_text(
            "This message cannot be stored.",
        )
        return

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO quote_db
            (message_id, chat_id, message_user_id, saver_user_id, forwarded_message_id)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                quote_message.message_id,
                quote_message.chat_id,
                quote_message.from_user.id,
                message.from_user.id,
                forwarded_message.message_id,
            ),
        )
        await conn.commit()

    await message.reply_text(
        f"Quote added by @{await utils.get_username(message.from_user.id, context)}.",
        parse_mode=ParseMode.HTML,
    )


@usage("/quote [OPTIONAL_USERNAME]")
@example("/quote @obviyus")
@triggers(["quote", "q"])
@description("Return a random message from QuotesDB for this group.")
async def get_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Get a quote from QuotesDB."""
    async with get_db(write=True) as conn:
        # Clean up old history entries (older than 10 quotes)
        await conn.execute(
            """
            DELETE FROM quote_recent_history
            WHERE chat_id = ? AND id NOT IN (
                SELECT id FROM quote_recent_history
                WHERE chat_id = ?
                ORDER BY shown_time DESC
                LIMIT 10
            );
            """,
            (message.chat_id, message.chat_id),
        )

        if context.args:
            author_username = context.args[0].replace("@", "")
            author_user_id = await utils.string.get_user_id_from_username(
                author_username
            )

            if not author_user_id:
                await message.reply_text(
                    f"@{escape(author_username)} not found.",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Get quotes excluding recently shown ones
            async with conn.execute(
                """
                SELECT * FROM quote_db
                WHERE chat_id = ? AND message_user_id = ?
                AND id NOT IN (
                    SELECT quote_id FROM quote_recent_history
                    WHERE chat_id = ?
                )
                ORDER BY RANDOM() LIMIT 1;
                """,
                (message.chat_id, author_user_id, message.chat_id),
            ) as cursor:
                row = await cursor.fetchone()

            # If no non-recent quotes available, fall back to any quote
            if not row:
                async with conn.execute(
                    """
                    SELECT * FROM quote_db
                    WHERE chat_id = ? AND message_user_id = ?
                    ORDER BY RANDOM() LIMIT 1;
                    """,
                    (message.chat_id, author_user_id),
                ) as cursor:
                    row = await cursor.fetchone()

            if not row:
                await message.reply_text(
                    f"No quotes found by @{escape(author_username)}.",
                    parse_mode=ParseMode.HTML,
                )
                return
        else:
            # Get quotes excluding recently shown ones
            async with conn.execute(
                """
                SELECT * FROM quote_db
                WHERE chat_id = ?
                AND id NOT IN (
                    SELECT quote_id FROM quote_recent_history
                    WHERE chat_id = ?
                )
                ORDER BY RANDOM() LIMIT 1;
                """,
                (message.chat_id, message.chat_id),
            ) as cursor:
                row = await cursor.fetchone()

            # If no non-recent quotes available, fall back to any quote
            if not row:
                async with conn.execute(
                    """
                    SELECT * FROM quote_db WHERE chat_id = ? ORDER BY RANDOM() LIMIT 1;
                    """,
                    (message.chat_id,),
                ) as cursor:
                    row = await cursor.fetchone()

            if not row:
                await message.reply_text(
                    "No quotes found in this chat.",
                    parse_mode=ParseMode.HTML,
                )
                return

        # Record this quote in recent history
        await conn.execute(
            """
            INSERT INTO quote_recent_history (chat_id, quote_id) VALUES (?, ?);
            """,
            (message.chat_id, row["id"]),
        )
        await conn.commit()

        try:
            await message.chat.forward_from(
                config["TELEGRAM"]["QUOTE_CHANNEL_ID"], row["forwarded_message_id"]
            )
        except BadRequest:
            await message.reply_text(
                "Quoted message deleted. Removing the quote.",
                parse_mode=ParseMode.HTML,
            )
            await conn.execute(
                """
                DELETE FROM quote_db WHERE id = ?;
                """,
                (row["id"],),
            )
            # Also remove from recent history if it was just added
            await conn.execute(
                """
                DELETE FROM quote_recent_history WHERE quote_id = ?;
                """,
                (row["id"],),
            )
            await conn.commit()
