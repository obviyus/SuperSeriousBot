import json
import uuid

import dateparser
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
    cursor = sqlite_conn.cursor()

    cursor.execute(
        """
        SELECT fts FROM group_settings
        WHERE chat_id = ?;
        """,
        (update.message.chat_id,),
    )

    setting = cursor.fetchone()

    if not setting or not setting["fts"]:
        await update.message.reply_text(
            "Full text search is not enabled in this chat. To enable it, use /enable_fts."
        )
        return

    if not context.args:
        await update.message.reply_text("Please provide a search query.")
        return

    query = " ".join(context.args)
    if update.message.reply_to_message:
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
            AND user_id = ?
            AND csf.message_text MATCH ? 
            ORDER BY RANDOM()
            LIMIT 1;
            """,
            (
                update.message.chat_id,
                update.message.reply_to_message.from_user.id,
                query,
            ),
        )
    else:
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
            AND csf.message_text MATCH ?
            ORDER BY RANDOM()
            LIMIT 1;
            """,
            (update.message.chat_id, query),
        )

    results = cursor.fetchone()
    if not results:
        await update.message.reply_text("No results found.")
        return

    await context.bot.forward_message(
        chat_id=update.message.chat_id,
        from_chat_id=update.message.chat_id,
        message_id=results["message_id"],
    )


@triggers(["enable_fts"])
@usage("/enable_fts")
@description("Enable full text search in the current chat.")
@example("/enable_fts")
async def enable_fts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enable full text search in the current chat.
    """
    # Check if user is a moderator
    chat_admins = await context.bot.get_chat_administrators(update.message.chat_id)
    if not update.message.from_user.id in [admin.user.id for admin in chat_admins]:
        await update.message.reply_text("You are not a moderator.")
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
        ON CONFLICT(chat_id) DO UPDATE SET fts = 1;
        """,
        (update.message.chat_id,),
    )

    await update.message.reply_text("Full text search has been enabled in this chat.")


@triggers(["import"])
@usage("/import")
@description("Import chat stats for a chat given the JSON export.")
@example("/import")
async def import_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Import chat stats for a chat given the JSON export.
    """
    if (
        not update.message.reply_to_message
        or not update.message.reply_to_message.document
    ):
        await update.message.reply_text("Please reply to a JSON file.")
        return

    document = update.message.reply_to_message.document
    if document.mime_type != "application/json":
        await update.message.reply_text("Please provide a JSON file.")
        return

    file = await document.get_file()
    filename = uuid.uuid4()
    await file.download_to_drive(f"{filename}.json")

    with open(f"{filename}.json", "r") as file:
        data = json.load(file)

    chat_id = data["id"]
    cursor = sqlite_conn.cursor()
    for message in data["messages"]:
        if message["type"] != "message" or not message["text"]:
            continue

        text_parts = []
        for part in message["text"]:
            if isinstance(part, dict):
                if part.get("type") == "bot_command":
                    text_parts.append(part.get("text", ""))
            else:
                text_parts.append(part)

        text = "".join(text_parts)

        user_id = message["from_id"].replace("user", "")
        create_time = dateparser.parse(message["date"])

        cursor.execute(
            """
            INSERT INTO chat_stats (chat_id, user_id, message_id, create_time, message_text)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id, message_id) DO NOTHING;
            """,
            (
                chat_id,
                user_id,
                message["id"],
                create_time,
                text,
            ),
        )

    sqlite_conn.commit()
    await update.message.reply_text("Chat stats imported.")
