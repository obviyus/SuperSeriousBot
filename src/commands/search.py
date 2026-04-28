import asyncio
import logging
import os
import random
import uuid

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from management.chat_memory import (
    chat_search,
    import_chat_stats_rows,
    is_fts_enabled,
    parse_export_file,
)
from management.chat_memory import (
    enable_fts as enable_chat_fts,
)
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

    author_id = (
        message.reply_to_message.from_user.id
        if message.reply_to_message and message.reply_to_message.from_user
        else None
    )
    results = await chat_search(message.chat_id, query, author_id)

    if not results:
        if not await is_fts_enabled(message.chat_id):
            await message.reply_text(
                "Full text search is not enabled in this chat. To enable it, use /enable_fts."
            )
            return
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

    await enable_chat_fts(message.chat_id)

    await message.reply_text("Full text search has been enabled in this chat.")


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
        batch = await asyncio.to_thread(parse_export_file, filename, message.chat_id)

        if not batch:
            await status_msg.edit_text("No valid messages found in export.")
            return

        await status_msg.edit_text(f"Importing {len(batch):,} messages...")
        await status_msg.edit_text("Rebuilding search index...")
        await import_chat_stats_rows(message.chat_id, batch)

        logging.info(f"Import completed: {len(batch):,} messages processed.")
        await status_msg.edit_text(
            f"Import complete! {len(batch):,} messages imported."
        )

    finally:
        try:
            os.remove(filename)
        except OSError:
            pass
