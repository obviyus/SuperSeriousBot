import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime

import ijson
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config.db import get_db
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


@triggers(["search"])
@usage("/search [SEARCH_QUERY]")
@description("Search for a message in the current chat for a user")
@example("/search japan")
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search command handler.
    """
    message = get_message(update)
    if not message:
        return

    if not context.args:
        await message.reply_text("Please provide a search query.")
        return

    query = " ".join(context.args)

    # Single connection for both queries
    async with get_db() as conn:
        async with conn.execute(
            "SELECT fts FROM group_settings WHERE chat_id = ?;",
            (message.chat_id,),
        ) as cursor:
            setting = await cursor.fetchone()

        if not setting or not setting["fts"]:
            await message.reply_text(
                "Full text search is not enabled in this chat. To enable it, use /enable_fts."
            )
            return

        # AIDEV-NOTE: chat_id is stored UNINDEXED in FTS5 table for fast filtering.
        # Filter by chat_id in FTS first, then join only matching rows.
        if message.reply_to_message and message.reply_to_message.from_user:
            sql = """
            SELECT cs.message_id
                FROM chat_stats_fts csf
                INNER JOIN chat_stats cs ON cs.id = csf.rowid
            WHERE csf.message_text MATCH ?
                AND csf.chat_id = ?
                AND cs.user_id = ?
                AND cs.message_text NOT LIKE '/%';
            """
            params = (
                query,
                message.chat_id,
                message.reply_to_message.from_user.id,
            )
        else:
            sql = """
            SELECT cs.message_id
                FROM chat_stats_fts csf
                INNER JOIN chat_stats cs ON cs.id = csf.rowid
            WHERE csf.message_text MATCH ?
                AND csf.chat_id = ?
                AND cs.message_text NOT LIKE '/%';
            """
            params = (query, message.chat_id)

        async with conn.execute(sql, params) as cursor:
            results = list(await cursor.fetchall())

    if not results:
        await message.reply_text("No results found.")
        return

    result = random.choice(results)
    await context.bot.forward_message(
        chat_id=message.chat_id,
        from_chat_id=message.chat_id,
        message_id=result["message_id"],
    )


@triggers(["enable_fts"])
@usage("/enable_fts")
@description("Enable full text search in the current chat.")
@example("/enable_fts")
async def enable_fts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """
    Enable full text search in the current chat.
    """
    if not message.from_user:
        return

    # Check if user is a moderator
    if message.chat.type != ChatType.PRIVATE:
        chat_admins = await context.bot.get_chat_administrators(message.chat_id)
        if message.from_user.id not in [admin.user.id for admin in chat_admins]:
            await message.reply_text("You are not a moderator.")
            return

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET fts = 1;
            """,
            (message.chat_id,),
        )
        await conn.commit()

    await message.reply_text("Full text search has been enabled in this chat.")


def _parse_export_file(filepath: str, chat_id: int) -> list[tuple]:
    """
    Parse Telegram JSON export file and return list of tuples for bulk insert.
    Runs in a thread pool to avoid blocking the event loop.
    """
    batch = []
    with open(filepath, "rb") as f:
        messages = ijson.items(f, "messages.item")

        for msg in messages:
            if msg["type"] != "message" or not msg["text"]:
                continue

            # Build message text from parts
            text_parts = []
            for part in msg["text"]:
                if isinstance(part, dict):
                    if part.get("type") == "bot_command":
                        text_parts.append(part.get("text", ""))
                else:
                    text_parts.append(part)

            text = "".join(text_parts)
            if not text:
                continue

            # Parse user_id
            from_id = msg.get("from_id", "")
            if not from_id:
                continue
            user_id = from_id.replace("user", "")

            # Fast ISO-8601 parse
            raw = msg["date"]
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                dt = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")

            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            create_time = dt.strftime("%Y-%m-%d %H:%M:%S")

            batch.append((chat_id, user_id, msg["id"], create_time, text))

    return batch


@triggers(["import"])
@usage("/import")
@description("Import chat stats for a chat given the JSON export.")
@example("/import")
async def import_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Import chat stats for a chat given the JSON export.

    AIDEV-NOTE: Performance optimizations applied:
    1. Parse entire file in thread pool (non-blocking)
    2. Disable FTS trigger during bulk insert
    3. Use executemany() for batch inserts
    4. Rebuild FTS index once at end (faster than per-row trigger)
    """
    message = get_message(update)
    if not message:
        return

    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("Please reply to a JSON file.")
        return

    document = message.reply_to_message.document
    if document.mime_type != "application/json":
        await message.reply_text("Please provide a JSON file.")
        return

    status_msg = await message.reply_text("Downloading file...")

    file = await document.get_file()
    filename = f"{uuid.uuid4()}.json"
    await file.download_to_drive(filename)

    try:
        await status_msg.edit_text("Parsing JSON export...")

        # Parse file in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        batch = await loop.run_in_executor(
            None, _parse_export_file, filename, message.chat_id
        )

        if not batch:
            await status_msg.edit_text("No valid messages found in export.")
            return

        await status_msg.edit_text(f"Importing {len(batch):,} messages...")

        async with get_db(write=True) as conn:
            # Optimize SQLite for bulk insert
            await conn.execute("PRAGMA synchronous = OFF;")
            await conn.execute("PRAGMA journal_mode = MEMORY;")

            # Disable FTS trigger for bulk insert (we'll rebuild index after)
            await conn.execute("DROP TRIGGER IF EXISTS chat_stats_ai;")

            # Bulk insert with executemany
            await conn.executemany(
                """
                INSERT INTO chat_stats (chat_id, user_id, message_id, create_time, message_text)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id, message_id) DO NOTHING;
                """,
                batch,
            )
            await conn.commit()

            await status_msg.edit_text("Rebuilding search index...")

            # Recreate FTS trigger
            await conn.execute(
                """
                CREATE TRIGGER chat_stats_ai AFTER INSERT ON chat_stats BEGIN
                    INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
                    VALUES (new.id, new.message_text, new.chat_id);
                END
                """
            )

            # Rebuild FTS index for newly inserted rows
            # Only index rows from this chat that aren't already in FTS
            await conn.execute(
                """
                INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
                SELECT cs.id, cs.message_text, cs.chat_id
                FROM chat_stats cs
                WHERE cs.chat_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM chat_stats_fts WHERE rowid = cs.id
                )
                """,
                (message.chat_id,),
            )
            await conn.commit()

            # Reset pragmas to safe defaults
            await conn.execute("PRAGMA synchronous = FULL;")
            await conn.execute("PRAGMA journal_mode = WAL;")

        logging.info(f"Import completed: {len(batch):,} messages processed.")
        await status_msg.edit_text(
            f"Import complete! {len(batch):,} messages imported."
        )

    finally:
        # Clean up temp file
        import os

        try:
            os.remove(filename)
        except OSError:
            pass
