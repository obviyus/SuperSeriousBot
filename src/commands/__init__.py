"""Commands for general use."""

import random
import traceback
from collections.abc import Awaitable, Callable
from functools import wraps
from importlib import import_module

from telegram import Message, Update
from telegram.constants import ChatAction, ParseMode, ReactionEmoji
from telegram.error import BadRequest
from telegram.ext import CommandHandler, ContextTypes

import utils
from config import logger
from config.db import get_db
from config.options import config
from utils.concurrency import schedule_background_task
from utils.decorators import CommandMeta, get_command_meta, get_registered_commands
from utils.messages import get_message

COMMAND_MODULE_NAMES = (
    "animals", "ask", "book", "calc", "define", "dl", "gif", "graph",
    "habit", "highlight", "hltb", "insult", "joke", "meme", "model", "ping",
    "quote", "remind", "search", "spurdo", "store", "summon", "tldr",
    "transcribe", "translate", "ud", "uwu", "weather", "whitelist",
)
MANAGEMENT_MODULE_NAMES = ("blocks", "botstats", "stats")

for module_name in COMMAND_MODULE_NAMES:
    import_module(f"{__name__}.{module_name}")
for module_name in MANAGEMENT_MODULE_NAMES:
    import_module(f"management.{module_name}")

habit = import_module(f"{__name__}.habit")
summon = import_module(f"{__name__}.summon")
highlight_button_handler = import_module(
    f"{__name__}.highlight"
).highlight_button_handler

# Import side effects above register decorated commands.
list_of_commands = get_registered_commands()

REACTION_MAP = {
    "good bot": [
        ReactionEmoji.HEART_WITH_ARROW, ReactionEmoji.SMILING_FACE_WITH_HEARTS,
        ReactionEmoji.HEART_ON_FIRE, ReactionEmoji.BANANA, ReactionEmoji.KISS_MARK,
        ReactionEmoji.MAN_TECHNOLOGIST, ReactionEmoji.NAIL_POLISH,
        ReactionEmoji.FACE_THROWING_A_KISS, ReactionEmoji.ALIEN_MONSTER,
    ],
    "bad bot": [
        ReactionEmoji.FEARFUL_FACE, ReactionEmoji.LOUDLY_CRYING_FACE,
        ReactionEmoji.BROKEN_HEART, ReactionEmoji.CRYING_FACE,
        ReactionEmoji.FACE_SCREAMING_IN_FEAR,
    ],
}

async def _record_command_stat(command: str, user_id: int) -> None:
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO command_stats (command, user_id) VALUES (?, ?);",
            (command, user_id),
        )


async def disabled(update: Update, _: ContextTypes.DEFAULT_TYPE):
    message = get_message(update)

    if not message:
        return
    await message.reply_text("❌ This command is disabled.")


async def every_message_action(update: Update, _: ContextTypes.DEFAULT_TYPE):
    message = get_message(update)

    if not message:
        return
    if message.text:
        text = message.text.lower()
        for trigger, emojis in REACTION_MAP.items():
            if trigger in text:
                try:
                    await message.set_reaction(random.choice(emojis))
                except BadRequest as exc:
                    logger.debug("Skipping auto reaction: %s", exc)
                break


type CommandHandler_T = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def command_wrapper(fn: CommandHandler_T):
    @wraps(fn)
    async def wrapped_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = get_message(update)
        if not message:
            return

        async def set_command_reaction() -> None:
            try:
                await message.set_reaction(ReactionEmoji.WRITING_HAND)
            except BadRequest as exc:
                logger.debug("Skipping command reaction: %s", exc)

        try:
            schedule_background_task(
                message.reply_chat_action(ChatAction.TYPING),
                "typing-indicator",
            )

            if message.from_user and message.text and message.text.startswith("/"):
                sent_command = message.text.split(maxsplit=1)[0].split("@")[0][1:].lower()
                async with get_db() as conn:
                    result = await conn.execute(
                        "SELECT 1 FROM command_blocklist WHERE user_id = ? AND command = ?",
                        (message.from_user.id, sent_command),
                    )
                    if await result.fetchone():
                        await message.reply_text(
                            "❌ You are blocked from using this command."
                        )
                        return
            else:
                sent_command = None

            schedule_background_task(
                set_command_reaction(),
                "command-reaction",
            )

            await fn(update, context)

            if sent_command and sent_command in command_triggers and message.from_user:
                schedule_background_task(
                    _record_command_stat(sent_command, message.from_user.id),
                    "command-stats",
                )

        except Exception as e:
            logger.error(f"Error in /{getattr(fn, '__name__', fn.__class__.__name__)}: {e!s}")
            logger.error(traceback.format_exc())

    return wrapped_command


command_handler_list = []
command_triggers: set[str] = set()


def _validate_command_meta(
    command: Callable[..., Awaitable[None]], meta: CommandMeta
) -> None:
    missing_fields = [
        field
        for field in ("triggers", "description", "usage", "example")
        if not getattr(meta, field)
    ]
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

    command_triggers.update(meta.triggers)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)

    if not message:
        return
    query = update.callback_query
    if not query or not query.data:
        return

    handler = {
        "hb": habit.habit_button_handler,
        "hl": highlight_button_handler,
        "sg": summon.summon_keyboard_button,
    }.get(query.data.split(":", 1)[0])
    if handler:
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

