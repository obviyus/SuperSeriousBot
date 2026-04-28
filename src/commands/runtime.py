import random
import traceback
from collections.abc import Callable, Coroutine
from functools import wraps

from telegram import Message, Update
from telegram.constants import ChatAction, ChatType, ParseMode, ReactionEmoji
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import logger
from config.db import get_db
from config.options import config
from utils.admin import is_admin
from utils.concurrency import schedule_background_task
from utils.decorators import CommandFunc, CommandMeta, get_command_meta
from utils.messages import get_message

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

type CommandHandler_T = Callable[
    [Update, ContextTypes.DEFAULT_TYPE],
    Coroutine[object, object, None],
]


async def record_command_stat(command: str, user_id: int) -> None:
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO command_stats (command, user_id) VALUES (?, ?);",
            (command, user_id),
        )


async def disabled(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if message:
        await message.reply_text("❌ This command is disabled.")


async def every_message_action(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.text:
        return

    text = message.text.lower()
    for trigger, emojis in REACTION_MAP.items():
        if trigger in text:
            try:
                await message.set_reaction(random.choice(emojis))
            except BadRequest as exc:
                logger.debug("Skipping auto reaction: %s", exc)
            return


async def _is_blocked(user_id: int, command: str) -> bool:
    async with get_db() as conn:
        result = await conn.execute(
            "SELECT 1 FROM command_blocklist WHERE user_id = ? AND command = ?",
            (user_id, command),
        )
        return bool(await result.fetchone())


def sent_command(message: Message) -> str | None:
    if not message.from_user or not message.text or not message.text.startswith("/"):
        return None
    return message.text.split(maxsplit=1)[0].split("@")[0][1:].lower()


async def ensure_command_available(
    message: Message,
    user_id: int,
    command: str,
    *,
    allow_private_whitelist: bool = False,
) -> bool:
    if is_admin(user_id):
        return True

    whitelist_chat_id = (
        user_id if message.chat.type == ChatType.PRIVATE else message.chat.id
    )
    if message.chat.type == ChatType.PRIVATE and not allow_private_whitelist:
        await message.reply_text("This command is not available in private chats.")
        return False

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT 1
            FROM command_whitelist
            WHERE command = ?
            AND (
                (whitelist_type = 'chat' AND whitelist_id = ?)
                OR (whitelist_type = 'user' AND whitelist_id = ?)
            );
            """,
            (command, whitelist_chat_id, user_id),
        ) as cursor:
            if await cursor.fetchone():
                return True

    if message.chat.type == ChatType.PRIVATE:
        await message.reply_text("This command is not available in private chats.")
        return False

    await message.reply_text(
        "This command is not available in this chat. "
        "Please contact an admin to whitelist this command."
    )
    return False


def command_wrapper(
    fn: CommandHandler_T,
    command_triggers: set[str],
) -> CommandHandler_T:
    @wraps(fn)
    async def wrapped_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

            command_name = sent_command(message)
            if command_name and message.from_user:
                if await _is_blocked(message.from_user.id, command_name):
                    await message.reply_text(
                        "❌ You are blocked from using this command."
                    )
                    return

            schedule_background_task(set_command_reaction(), "command-reaction")

            await fn(update, context)

            if command_name and command_name in command_triggers and message.from_user:
                schedule_background_task(
                    record_command_stat(command_name, message.from_user.id),
                    "command-stats",
                )
        except Exception as exc:
            logger.error(
                f"Error in /{getattr(fn, '__name__', fn.__class__.__name__)}: {exc!s}"
            )
            logger.error(traceback.format_exc())

    return wrapped_command


def validate_command_meta(command: CommandFunc, meta: CommandMeta) -> None:
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


def is_command_enabled(command: CommandFunc) -> bool:
    meta = get_command_meta(command)
    required_key = meta.api_key if meta else None
    if not required_key:
        return True

    return bool(
        getattr(config.API, required_key, "")
        or getattr(config.TELEGRAM, required_key, "")
    )


async def usage_string(message: Message, func: CommandFunc) -> None:
    meta = get_command_meta(func)
    if not meta:
        module_name = getattr(func, "__module__", func.__class__.__module__)
        command_name = getattr(func, "__name__", func.__class__.__name__)
        raise RuntimeError(
            f"{module_name}.{command_name} is not a decorated command."
        )
    validate_command_meta(func, meta)
    assert meta.description is not None
    assert meta.usage is not None
    assert meta.example is not None

    await message.reply_text(
        f"{meta.description}\n\n<b>Usage:</b>\n<pre>{meta.usage}</pre>\n\n<b>Example:</b>\n<pre>{meta.example}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
