import asyncio
import os
import time
import uuid

from telegram import Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from commands.runtime import ensure_command_available
from config.logger import logger
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

SEARCH_STATUS = "Searching messages..."
SEARCH_STATUS_EDIT_INTERVAL_SECONDS = 0.8
TELEGRAM_MESSAGE_LIMIT = 4096


def search_status_text(reasoning: str) -> str:
    prefix = f"{SEARCH_STATUS}\n\n"
    available = TELEGRAM_MESSAGE_LIMIT - len(prefix)
    body = reasoning.strip()
    if len(body) > available:
        body = f"…{body[-(available - 1) :]}"
    return prefix + body


@command(
    triggers=["search"],
    usage="/search [QUESTION]",
    example="/search what job does Nathu do",
    description=(
        "Answer from this chat's message history. "
        "Reply to someone to search only their messages."
    ),
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
        await message.reply_text(
            "Ask a question after /search. "
            "Reply to someone to search only their messages."
        )
        return

    query = " ".join(context.args)
    author_id = (
        message.reply_to_message.from_user.id
        if message.reply_to_message and message.reply_to_message.from_user
        else None
    )

    status_message = await message.reply_text(SEARCH_STATUS)
    last_status_edit = 0.0
    last_status_text = SEARCH_STATUS
    status_updates_enabled = True

    async def show_reasoning(reasoning: str) -> None:
        nonlocal last_status_edit, last_status_text, status_updates_enabled
        now = time.monotonic()
        text = search_status_text(reasoning)
        if (
            not status_updates_enabled
            or text == last_status_text
            or now - last_status_edit < SEARCH_STATUS_EDIT_INTERVAL_SECONDS
        ):
            return
        try:
            await status_message.edit_text(text)
        except TelegramError:
            status_updates_enabled = False
            logger.exception("Search status update failed")
            return
        last_status_edit = now
        last_status_text = text

    try:
        answer = await semantic_search_answer(
            message.chat_id,
            query,
            author_id,
            show_reasoning,
        )
    finally:
        try:
            await status_message.delete()
        except TelegramError:
            logger.exception("Search status deletion failed")

    if not answer:
        if not await is_fts_enabled(message.chat_id):
            await message.reply_text(
                "Chat search isn't enabled here. An admin can run /enable_fts."
            )
            return
        await message.reply_text(
            "I couldn't find anything from them about that."
            if author_id is not None
            else "I couldn't find anything about that."
        )
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

        logger.info("Import completed: %s messages processed.", f"{len(batch):,}")
        await status_msg.edit_text(
            f"Import complete! {len(batch):,} messages imported."
        )

    finally:
        try:
            os.remove(filename)
        except OSError:
            pass
