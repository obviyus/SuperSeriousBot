"""Commands for general use."""

import random
import traceback
from collections.abc import Awaitable, Callable
from functools import wraps

from telegram import Message, MessageEntity, Update
from telegram.constants import ChatAction, ParseMode, ReactionEmoji
from telegram.ext import CommandHandler, ContextTypes

import utils
from config import logger
from config.db import get_db
from config.options import config
from management import blocks, botstats, stats
from utils.concurrency import schedule_background_task
from utils.decorators import CommandMeta, get_command_meta
from utils.messages import get_message

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
    transcribe,
    translate,
    ud,
    uwu,
    weather,
    whitelist,
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
    transcribe,
    translate,
    ud,
    uwu,
    weather,
    whitelist,
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
        stats.get_user_stats,
    ]
)

REACTION_MAP = {
    "good bot": [
        ReactionEmoji.HEART_WITH_ARROW,
        ReactionEmoji.SMILING_FACE_WITH_HEARTS,
        ReactionEmoji.HEART_ON_FIRE,
        ReactionEmoji.BANANA,
        ReactionEmoji.KISS_MARK,
        ReactionEmoji.MAN_TECHNOLOGIST,
        ReactionEmoji.NAIL_POLISH,
        ReactionEmoji.FACE_THROWING_A_KISS,
        ReactionEmoji.ALIEN_MONSTER,
    ],
    "bad bot": [
        ReactionEmoji.FEARFUL_FACE,
        ReactionEmoji.LOUDLY_CRYING_FACE,
        ReactionEmoji.BROKEN_HEART,
        ReactionEmoji.CRYING_FACE,
        ReactionEmoji.FACE_SCREAMING_IN_FEAR,
    ],
}


async def _record_command_stat(command: str, user_id: int) -> None:
    async with get_db(write=True) as conn:
        await conn.execute(
            "INSERT INTO command_stats (command, user_id) VALUES (?, ?);",
            (command, user_id),
        )
        await conn.commit()


async def disabled(update: Update, _: ContextTypes.DEFAULT_TYPE):
    message = get_message(update)

    if not message:
        return
    """Disabled command handler."""
    await message.reply_text("❌ This command is disabled.")


async def every_message_action(update: Update, _: ContextTypes.DEFAULT_TYPE):
    message = get_message(update)

    if not message:
        return
    """Every message action handler."""
    if message and message.text:
        text = message.text.lower()
        for trigger, emojis in REACTION_MAP.items():
            if trigger in text:
                await message.set_reaction(random.choice(emojis))
                break


async def is_user_blocked(user_id: int, command: str) -> bool:
    async with get_db() as conn:
        result = await conn.execute(
            "SELECT 1 FROM command_blocklist WHERE user_id = ? AND command = ?",
            (user_id, command),
        )
        return bool(await result.fetchone())


type CommandHandler_T = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def command_wrapper(fn: CommandHandler_T):
    @wraps(fn)
    async def wrapped_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = get_message(update)
        if not message:
            return

        try:
            sent_command = None
            if message.from_user:
                sent_command_entity = next(
                    iter(message.parse_entities([MessageEntity.BOT_COMMAND]).values()),
                    None,
                )
                if sent_command_entity:
                    sent_command = sent_command_entity.split("@")[0][1:]

            # Check if user is blocked before doing anything expensive
            if sent_command and message.from_user:
                if await is_user_blocked(message.from_user.id, sent_command):
                    await message.reply_text(
                        "❌ You are blocked from using this command."
                    )
                    return

            schedule_background_task(
                message.set_reaction(ReactionEmoji.WRITING_HAND),
                "command-reaction",
            )
            schedule_background_task(
                message.reply_chat_action(ChatAction.TYPING),
                "typing-indicator",
            )

            await fn(update, context)

            if sent_command and sent_command in command_doc_list and message.from_user:
                schedule_background_task(
                    _record_command_stat(sent_command, message.from_user.id),
                    "command-stats",
                )

        except Exception as e:
            logger.error(f"Error in /{fn.__name__}: {e!s}")  # type: ignore[attr-defined]
            logger.error(traceback.format_exc())

    return wrapped_command


command_handler_list = []
command_doc_list: dict[str, dict[str, str]] = {}


def _validate_command_meta(
    command: Callable[..., Awaitable[None]], meta: CommandMeta
) -> None:
    missing_fields: list[str] = []
    if not meta.triggers:
        missing_fields.append("triggers")
    if not meta.description:
        missing_fields.append("description")
    if not meta.usage:
        missing_fields.append("usage")
    if not meta.example:
        missing_fields.append("example")

    if missing_fields:
        module_name = getattr(command, "__module__", command.__class__.__module__)
        command_name = getattr(command, "__name__", command.__class__.__name__)
        raise RuntimeError(
            f"Command {module_name}.{command_name} missing metadata: "
            f"{', '.join(missing_fields)}"
        )


def is_command_enabled(command: Callable[..., Awaitable[None]]) -> bool:
    meta = get_command_meta(command)
    required_key = meta.api_key if meta else None
    if not required_key:
        return True

    return bool(
        config.get("API", {}).get(required_key)
        or config.get("TELEGRAM", {}).get(required_key)
    )


for command in list_of_commands:
    meta = get_command_meta(command)
    if not meta:
        continue

    _validate_command_meta(command, meta)
    assert meta.triggers is not None
    assert meta.description is not None
    assert meta.usage is not None
    assert meta.example is not None

    handler = command if is_command_enabled(command) else disabled
    handler = command_wrapper(handler)

    command_handler_list.append(CommandHandler(meta.triggers, handler))

    for trigger in meta.triggers:
        command_doc_list[trigger] = {
            "description": meta.description,
            "usage": meta.usage,
            "example": meta.example,
        }


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)

    if not message:
        return
    query = update.callback_query
    if not query or not query.data:
        return

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
    meta = get_command_meta(func)
    if not meta:
        raise RuntimeError(
            f"{func.__module__}.{func.__name__} is not a decorated command."
        )
    _validate_command_meta(func, meta)
    assert meta.description is not None
    assert meta.usage is not None
    assert meta.example is not None

    await message.reply_text(
        f"{meta.description}\n\n<b>Usage:</b>\n<pre>{meta.usage}</pre>\n\n<b>Example:</b>\n<pre>{meta.example}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def save_mentions(
    mentioning_user_id: int, mentioned_users: set[str], message: Message
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
