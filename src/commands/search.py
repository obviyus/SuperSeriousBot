from telegram import Update
from telegram.ext import ContextTypes

from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


@triggers(["search"])
@usage("/search [SEARCH_QUERY]")
@description("Search for a message in the current chat for a user")
@example("/search japan")
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search command handler.
    """
    if not update.message.reply_to_message:
        await update.message.reply_text("Please reply to a user to search.")
        return

    if not context.args:
        await update.message.reply_text("Please provide a search query.")
        return

    query = " ".join(context.args)

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT
            cs.id,
            cs.chat_id,
            cs.message_id,
            cs.create_time,
            cs.user_id,
            cs.message_text
        FROM chat_stats cs
        INNER JOIN chat_stats_fts csf ON cs.id = csf.rowid
        WHERE chat_id = ? 
        AND csf.message_text MATCH ?;
        """,
        (update.message.chat_id, query),
    )

    results = cursor.fetchall()
    if not results:
        await update.message.reply_text("No results found.")
        return

    await context.bot.forward_message(
        chat_id=update.message.chat_id,
        from_chat_id=update.message.chat_id,
        message_id=results[0]["message_id"],
    )
