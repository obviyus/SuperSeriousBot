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

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM quote_db WHERE message_id = ?;
            """,
            (quote_message.message_id,),
        ) as cursor:
            if await cursor.fetchone():
                await update.message.reply_text(
                    "This message has already been saved.",
                    parse_mode=ParseMode.HTML,
                )
                return

    try:
        forwarded_message = await quote_message.forward(
            chat_id=config["TELEGRAM"]["QUOTE_CHANNEL_ID"],
        )
    except BadRequest:
        await update.message.reply_text(
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
                update.message.from_user.id,
                forwarded_message.message_id,
            ),
        )
        await conn.commit()

    await update.message.reply_text(
        f"Quote added by @{await utils.get_username(update.message.from_user.id, context)}.",
        parse_mode=ParseMode.HTML,
    )


@usage("/quote [OPTIONAL_USERNAME]")
@example("/quote @obviyus")
@triggers(["quote", "q"])
@description("Return a random message from QuotesDB for this group.")
async def get_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a quote from QuotesDB."""
    async with get_db() as conn:
        if context.args:
            author_username = context.args[0].replace("@", "")
            author_user_id = await utils.string.get_user_id_from_username(
                author_username
            )

            if not author_user_id:
                await update.message.reply_text(
                    f"@{escape(author_username)} not found.",
                    parse_mode=ParseMode.HTML,
                )
                return

            async with conn.execute(
                """
                SELECT * FROM quote_db 
                WHERE chat_id = ? AND message_user_id = ? 
                ORDER BY RANDOM() LIMIT 1;
                """,
                (update.message.chat_id, author_user_id),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                await update.message.reply_text(
                    f"No quotes found by @{escape(author_username)}.",
                    parse_mode=ParseMode.HTML,
                )
                return
        else:
            async with conn.execute(
                """
                SELECT * FROM quote_db WHERE chat_id = ? ORDER BY RANDOM() LIMIT 1;
                """,
                (update.message.chat_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                await update.message.reply_text(
                    "No quotes found in this chat.",
                    parse_mode=ParseMode.HTML,
                )
                return

        try:
            await update.message.chat.forward_from(
                config["TELEGRAM"]["QUOTE_CHANNEL_ID"], row["forwarded_message_id"]
            )
        except BadRequest:
            await update.message.reply_text(
                "Quoted message deleted. Removing the quote.",
                parse_mode=ParseMode.HTML,
            )
            await conn.execute(
                """
                DELETE FROM quote_db WHERE id = ?;
                """,
                (row["id"],),
            )
            await conn.commit()
