from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import commands
import utils
from config import config
from config.db import get_db
from utils.decorators import command
from utils.messages import get_message


async def _fetch_random_quote(conn, query_conditions: str, params: list[int], chat_id: int):
    async with conn.execute(
        f"SELECT * FROM quote_db {query_conditions} AND id NOT IN (SELECT quote_id FROM quote_recent_history WHERE chat_id = ?) ORDER BY RANDOM() LIMIT 1;",
        (*params, chat_id),
    ) as cursor:
        return await cursor.fetchone()


@command(
    triggers=["addquote"],
    usage="/addquote",
    example="/addquote",
    description="Reply to a message to save it into QuotesDB.",
    api_key="QUOTE_CHANNEL_ID",
)
async def add_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await commands.usage_string(message, add_quote)
        return

    if message.has_protected_content:
        await message.reply_text(
            "This is protected and cannot be forwarded.",
        )
        return

    quote_message = message.reply_to_message
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
            await message.reply_text("This message cannot be stored.")
            return

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

    await message.reply_text(
        f"Quote added by @{await utils.get_username(message.from_user.id, context)}.",
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["quote", "q"],
    usage="/quote [OPTIONAL_USERNAME]",
    example="/quote @obviyus",
    description="Return a random message from QuotesDB for this group.",
)
async def get_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    async with get_db() as conn:
        params = [message.chat_id]
        query_conditions = "WHERE chat_id = ?"
        clear_history_sql = "DELETE FROM quote_recent_history WHERE chat_id = ?;"
        clear_history_params = (message.chat_id,)
        no_quote_text = "No quotes found in this chat."

        if context.args:
            author_username = context.args[0].replace("@", "")
            author_user_id = await utils.get_user_id_from_username(author_username)
            if not author_user_id:
                await message.reply_text(
                    f"@{escape(author_username)} not found.",
                    parse_mode=ParseMode.HTML,
                )
                return
            query_conditions += " AND message_user_id = ?"
            params.append(author_user_id)
            clear_history_sql = """
                DELETE FROM quote_recent_history
                WHERE chat_id = ? AND quote_id IN (
                    SELECT id FROM quote_db WHERE message_user_id = ?
                );
                """
            clear_history_params = (message.chat_id, author_user_id)
            no_quote_text = f"No quotes found by @{escape(author_username)}."

        row = await _fetch_random_quote(conn, query_conditions, params, message.chat_id)
        if not row:
            await conn.execute(clear_history_sql, clear_history_params)
            row = await _fetch_random_quote(conn, query_conditions, params, message.chat_id)

        if not row:
            await message.reply_text(no_quote_text, parse_mode=ParseMode.HTML)
            return

        # Record this quote in recent history
        await conn.execute(
            """
            INSERT INTO quote_recent_history (chat_id, quote_id) VALUES (?, ?);
            """,
            (message.chat_id, row["id"]),
        )

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
