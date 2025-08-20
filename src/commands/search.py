import asyncio
import logging
import uuid
from datetime import datetime

import ijson
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config.db import get_db
from utils.decorators import description, example, triggers, usage


@triggers(["search"])
@usage("/search [SEARCH_QUERY]")
@description("Search for a message in the current chat for a user")
@example("/search japan")
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search command handler.
    """
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT fts FROM group_settings
            WHERE chat_id = ?;
            """,
            (update.message.chat_id,),
        ) as cursor:
            setting = await cursor.fetchone()

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
        sql = """
        SELECT cs.id, cs.chat_id, cs.message_id, cs.create_time, cs.user_id, cs.message_text
            FROM chat_stats cs
            INNER JOIN chat_stats_fts csf ON cs.id = csf.rowid
        WHERE cs.chat_id = ?
            AND cs.user_id = ?
            AND csf.message_text MATCH ?
            AND cs.message_text NOT LIKE '/%'
        ORDER BY RANDOM()
        LIMIT 1;
        """
        params = (
            update.message.chat_id,
            update.message.reply_to_message.from_user.id,
            query,
        )
    else:
        sql = """
        SELECT cs.id, cs.chat_id, cs.message_id, cs.create_time, cs.user_id, cs.message_text
            FROM chat_stats cs
            INNER JOIN chat_stats_fts csf ON cs.id = csf.rowid
        WHERE cs.chat_id = ?
            AND csf.message_text MATCH ?
            AND cs.message_text NOT LIKE '/%'
        ORDER BY RANDOM()
        LIMIT 1;
        """
        params = (update.message.chat_id, query)

    async with get_db() as conn:
        async with conn.execute(sql, params) as cursor:
            results = await cursor.fetchone()

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
    if update.message.chat.type != ChatType.PRIVATE:
        chat_admins = await context.bot.get_chat_administrators(update.message.chat_id)
        if update.message.from_user.id not in [admin.user.id for admin in chat_admins]:
            await update.message.reply_text("You are not a moderator.")
            return

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET fts = 1;
            """,
            (update.message.chat_id,),
        )
        await conn.commit()

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

    async with get_db(write=True) as conn:
        await conn.execute("PRAGMA journal_mode=WAL;")

        processed_lines = 0
        loop = asyncio.get_running_loop()
        with await loop.run_in_executor(None, open, f"{filename}.json", "rb") as file:
            messages = ijson.items(file, "messages.item")

            for message in messages:
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
                # Fast ISO-8601 parse: handle 'Z' and offsets, store as
                # 'YYYY-MM-DD HH:MM:SS' in UTC for SQLite-friendly comparisons
                raw = message["date"]
                if raw.endswith("Z"):
                    raw = raw[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(raw)
                except ValueError:
                    # Fallback if string has no offset or unusual format
                    dt = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
                if dt.tzinfo is not None:
                    dt = dt.astimezone(datetime.UTC).replace(tzinfo=None)
                create_time = dt.strftime("%Y-%m-%d %H:%M:%S")

                await conn.execute(
                    """
                    INSERT INTO chat_stats (chat_id, user_id, message_id, create_time, message_text)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id, user_id, message_id) DO NOTHING;
                    """,
                    (
                        update.message.chat_id,
                        user_id,
                        message["id"],
                        create_time,
                        text,
                    ),
                )
                processed_lines += 1
                if processed_lines % 1000 == 0:
                    logging.info(f"Processed {processed_lines} lines.")
                    await conn.commit()

        await conn.commit()
        logging.info("Processing completed.")

    await update.message.reply_text("Chat stats imported.")
