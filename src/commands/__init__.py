"""
Commands for general use.
"""

import asyncio
import random
import traceback
from functools import wraps
from typing import Callable, Dict, List, Set

from telegram import Message, MessageEntity, Update
from telegram.constants import ChatAction, ParseMode, ReactionEmoji
from telegram.ext import CommandHandler, ContextTypes

import utils
from config import logger
from config.db import get_db
from config.options import config
from management import blocks, botstats, stats
from . import (
    animals,
    ask,
    book,
    calc,
    define,
    dl,
    gif,
    graph,
    habit,
    highlight,
    hltb,
    insult,
    joke,
    meme,
    model,
    ping,
    quote,
    remind,
    search,
    spurdo,
    store,
    summon,
    tldr,
    tldw,
    transcribe,
    translate,
    ud,
    uwu,
    weather,
)
from .highlight import highlight_button_handler

# Import all command functions
COMMAND_MODULES = [
    animals,
    ask,
    book,
    blocks,
    calc,
    define,
    dl,
    gif,
    graph,
    habit,
    highlight,
    hltb,
    insult,
    joke,
    meme,
    model,
    ping,
    quote,
    remind,
    search,
    spurdo,
    store,
    summon,
    tldr,
    tldw,
    transcribe,
    translate,
    ud,
    uwu,
    weather,
]

# Collect all command functions
list_of_commands = []
for module in COMMAND_MODULES:
    list_of_commands.extend(
        [
            getattr(module, name)
            for name in dir(module)
            if callable(getattr(module, name)) and not name.startswith("_")
        ]
    )

# Add management and stats functions
list_of_commands.extend(
    [
        botstats.get_command_stats,
        botstats.get_object_stats,
        botstats.get_total_chats,
        botstats.get_total_users,
        botstats.get_uptime,
        stats.get_chat_stats,
        stats.get_last_seen,
        stats.get_total_chat_stats,
    ]
)

POSITIVE_EMOJIS = [
    ReactionEmoji.HEART_WITH_ARROW,
    ReactionEmoji.SMILING_FACE_WITH_HEARTS,
    ReactionEmoji.HEART_ON_FIRE,
    ReactionEmoji.BANANA,
    ReactionEmoji.KISS_MARK,
    ReactionEmoji.MAN_TECHNOLOGIST,
    ReactionEmoji.NAIL_POLISH,
    ReactionEmoji.FACE_THROWING_A_KISS,
    ReactionEmoji.ALIEN_MONSTER,
]

NEGATIVE_EMOJIS = [
    ReactionEmoji.FEARFUL_FACE,
    ReactionEmoji.LOUDLY_CRYING_FACE,
    ReactionEmoji.BROKEN_HEART,
    ReactionEmoji.CRYING_FACE,
    ReactionEmoji.FACE_SCREAMING_IN_FEAR,
]


async def disabled(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Disabled command handler."""
    await update.message.reply_text("❌ This command is disabled.")


def get_random_item_from_list(items: List):
    return random.choice(items)


async def every_message_action(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Every message action handler."""
    if update.message and update.message.text:
        text = update.message.text.lower()
        if "good bot" in text:
            await update.message.set_reaction(
                get_random_item_from_list(POSITIVE_EMOJIS)
            )
        elif "bad bot" in text:
            await update.message.set_reaction(
                get_random_item_from_list(NEGATIVE_EMOJIS)
            )


async def is_user_blocked(user_id: int, command: str) -> bool:
    async with get_db() as conn:
        result = await conn.execute(
            "SELECT 1 FROM command_blocklist WHERE user_id = ? AND command = ?",
            (user_id, command),
        )
        return bool(await result.fetchone())


def command_wrapper(fn: Callable):
    @wraps(fn)
    async def wrapped_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        if not message:
            return

        try:
            # Check if user is blocked
            sent_command = next(
                iter(
                    update.message.parse_entities([MessageEntity.BOT_COMMAND]).values()
                ),
                None,
            )
            if sent_command:
                sent_command = sent_command.split("@")[0][1:]
                if await is_user_blocked(update.message.from_user.id, sent_command):
                    await message.reply_text(
                        "❌ You are blocked from using this command."
                    )
                    return

            tasks = [
                message.set_reaction(ReactionEmoji.WRITING_HAND),
                message.reply_chat_action(ChatAction.TYPING),
                fn(update, context),
            ]

            await asyncio.gather(*tasks)

            if sent_command and sent_command in command_doc_list:
                async with get_db(write=True) as conn:
                    await conn.execute(
                        "INSERT INTO command_stats (command, user_id) VALUES (?, ?);",
                        (sent_command, update.message.from_user.id),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"Error in /{fn.__name__}: {str(e)}")
            logger.error(traceback.format_exc())

    return wrapped_command


command_handler_list = []
command_doc_list: Dict[str, Dict[str, str]] = {}

for command in list_of_commands:
    if hasattr(command, "triggers"):
        handler = (
            command
            if not hasattr(command, "api_key") or command.api_key in config["API"]
            else disabled
        )
        handler = command_wrapper(handler)

        command_handler_list.append(CommandHandler(command.triggers, handler))

        for trigger in command.triggers:
            command_doc_list[trigger] = {
                "description": getattr(
                    command, "description", "No description available"
                ),
                "usage": getattr(command, "usage", "No usage information available"),
                "example": getattr(command, "example", "No example available"),
            }


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    handlers = {
        "hb": habit.habit_button_handler,
        "hl": highlight_button_handler,
        "sg": summon.summon_keyboard_button,
    }

    for prefix, handler in handlers.items():
        if query.data.startswith(prefix):
            await handler(update, context)
            return

    await query.answer("No function found for this button.")


async def usage_string(message: Message, func) -> None:
    """Return the usage string for a command."""
    await message.reply_text(
        f"{func.description}\n\n<b>Usage:</b>\n<pre>{func.usage}</pre>\n\n<b>Example:</b>\n<pre>{func.example}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def save_mentions(
    mentioning_user_id: int, mentioned_users: Set[str], message: Message
) -> None:
    """Save a mention in the database."""
    for user in mentioned_users:
        user_id = (
            await utils.get_user_id_from_username(user)
            if isinstance(user, str)
            else user
        )
        if user_id is not None:
            async with get_db(write=True) as conn:
                await conn.execute(
                    """
                    INSERT INTO chat_mentions (mentioning_user_id, mentioned_user_id, chat_id, message_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (mentioning_user_id, user_id, message.chat.id, message.message_id),
                )
                await conn.commit()
