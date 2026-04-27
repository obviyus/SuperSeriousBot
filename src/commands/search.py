import asyncio
import logging
import os
import random
import uuid
from datetime import UTC, datetime

import ijson
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config.db import get_db
from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["search"],
    usage="/search [SEARCH_QUERY]",
    example="/search japan",
    description="Search for a message in the current chat for a user",
)
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

        author_id = (
            message.reply_to_message.from_user.id
            if message.reply_to_message and message.reply_to_message.from_user
            else None
        )
        sql = """
        SELECT cs.message_id
            FROM chat_stats_fts csf
            INNER JOIN chat_stats cs ON cs.id = csf.rowid
        WHERE csf.message_text MATCH ?
            AND csf.chat_id = ?
            AND (? IS NULL OR cs.user_id = ?)
            AND cs.message_text NOT LIKE '/%';
        """
        params = (query, message.chat_id, author_id, author_id)

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


@command(
    triggers=["enable_fts"],
    usage="/enable_fts",
    example="/enable_fts",
    description="Enable full text search in the current chat.",
)
async def enable_fts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not message.from_user:
        return

    # Check if user is a moderator
    if message.chat.type != ChatType.PRIVATE:
        chat_admins = await context.bot.get_chat_administrators(message.chat_id)
        if message.from_user.id not in [admin.user.id for admin in chat_admins]:
            await message.reply_text("You are not a moderator.")
            return

    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET fts = 1;
            """,
            (message.chat_id,),
        )

    await message.reply_text("Full text search has been enabled in this chat.")


def _parse_export_file(filepath: str, chat_id: int) -> list[tuple]:
    batch = []
    with open(filepath, "rb") as f:
        for msg in ijson.items(f, "messages.item"):
            if msg["type"] != "message" or not msg["text"] or not (from_id := msg.get("from_id")):
                continue

            text = "".join(
                part.get("text", "")
                if isinstance(part, dict) and part.get("type") == "bot_command"
                else part if isinstance(part, str)
                else ""
                for part in msg["text"]
            )
            if not text:
                continue

            raw = msg["date"]
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                dt = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)

            batch.append(
                (
                    chat_id,
                    from_id.replace("user", ""),
                    msg["id"],
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                    text,
                )
            )

    return batch


@command(
    triggers=["import"],
    usage="/import",
    example="/import",
    description="Import chat stats for a chat given the JSON export.",
)
async def import_chat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    filename = f"{uuid.uuid4()}.json"
    await (await document.get_file()).download_to_drive(filename)

    try:
        await status_msg.edit_text("Parsing JSON export...")
        batch = await asyncio.to_thread(_parse_export_file, filename, message.chat_id)

        if not batch:
            await status_msg.edit_text("No valid messages found in export.")
            return

        await status_msg.edit_text(f"Importing {len(batch):,} messages...")

        async with get_db() as conn:
            await conn.execute("PRAGMA synchronous = OFF;")
            await conn.execute("PRAGMA journal_mode = MEMORY;")
            await conn.execute("DROP TRIGGER IF EXISTS chat_stats_ai;")
            await conn.executemany(
                """
                INSERT INTO chat_stats (chat_id, user_id, message_id, create_time, message_text)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id, message_id) DO NOTHING;
                """,
                batch,
            )

            await status_msg.edit_text("Rebuilding search index...")
            await conn.execute(
                """
                CREATE TRIGGER chat_stats_ai AFTER INSERT ON chat_stats BEGIN
                    INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
                    VALUES (new.id, new.message_text, new.chat_id);
                END
                """
            )

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

            await conn.execute("PRAGMA synchronous = FULL;")
            await conn.execute("PRAGMA journal_mode = WAL;")

        logging.info(f"Import completed: {len(batch):,} messages processed.")
        await status_msg.edit_text(
            f"Import complete! {len(batch):,} messages imported."
        )

    finally:
        try:
            os.remove(filename)
        except OSError:
            pass
