import asyncio
import logging
import os
import uuid

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from commands.runtime import ensure_command_available
from management.chat_memory import (
    enable_fts as enable_chat_fts,
)
from management.chat_memory import (
    import_chat_stats_rows,
    is_fts_enabled,
    parse_export_file,
)
from management.chat_semantic_search import semantic_search_answer
from utils.command_limits import ensure_quota
from utils.decorators import command
from utils.messages import get_message, reply_markdown_or_plain


@command(
    triggers=["search"],
    usage="/search [SEARCH_QUERY]",
    example="/search what job does Nathu do",
    description="Answer a question using this chat's search history.",
    api_key="OPENROUTER_API_KEY",
)
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return

    if not await ensure_command_available(message, message.from_user.id, "search"):
        return
    if not await ensure_quota(message, message.from_user.id, "search"):
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

    try:
        answer = await semantic_search_answer(message.chat_id, query, author_id)
    except Exception:
        logging.exception("Semantic search failed for chat %s", message.chat_id)
        await message.reply_text("Search failed. Please try again.")
        return

    if not answer:
        if not await is_fts_enabled(message.chat_id):
            await message.reply_text(
                "Full text search is not enabled in this chat. To enable it, use /enable_fts."
            )
            return
        await message.reply_text("No results found.")
        return

    await reply_markdown_or_plain(
        message,
        answer,
        disable_web_page_preview=True,
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
    if not message.from_user:
        return

    if message.chat.type != ChatType.PRIVATE:
        chat_admins = await context.bot.get_chat_administrators(message.chat_id)
        if message.from_user.id not in [admin.user.id for admin in chat_admins]:
            await message.reply_text("You are not a moderator.")
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
