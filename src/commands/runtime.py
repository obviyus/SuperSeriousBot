import random
import time
import traceback
from collections.abc import Callable, Coroutine
from functools import wraps

from telegram import Message, Update
from telegram.constants import ChatAction, ChatType, ParseMode, ReactionEmoji
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from config import logger
from config.db import get_db
from config.options import config
from utils.admin import is_admin
from utils.concurrency import schedule_background_task
from utils.decorators import CommandFunc, get_command_meta
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


class HandledCommandError(Exception):
    """The command already showed the user a specific failure message."""


async def record_command_event(
    message: Message,
    command: str,
    status: str,
    duration_ms: int,
    error: Exception | None,
) -> None:
    user = message.from_user
    if not user:
        return

    text = message.text or ""
    _, separator, input_text = text.partition(" ")
    username = f"@{user.username}" if user.username else user.full_name
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO command_stats (
                command, user_id, chat_id, message_id, username, input_text,
                status, duration_ms, error_type, error_message, error_traceback
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command,
                user.id,
                message.chat_id,
                message.message_id,
                username,
                input_text.strip() if separator else None,
                status,
                duration_ms,
                type(error).__name__ if error else None,
                str(error) if error else None,
                "".join(traceback.format_exception(error)) if error else None,
            ),
        )


def finish_command_event(
    message: Message,
    command: str,
    status: str,
    start_time: float,
    error: Exception | None,
) -> None:
    duration_ms = round((time.perf_counter() - start_time) * 1000)
    log = logger.error if error else logger.info
    log(
        "command_event command=%s status=%s duration_ms=%s chat_id=%s "
        "message_id=%s user_id=%s error_type=%s",
        command,
        status,
        duration_ms,
        message.chat_id,
        message.message_id,
        message.from_user.id if message.from_user else None,
        type(error).__name__ if error else None,
        exc_info=(type(error), error, error.__traceback__) if error else None,
    )
    schedule_background_task(
        record_command_event(message, command, status, duration_ms, error),
        "command-event",
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

    async with (
        get_db() as conn,
        conn.execute(
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
        ) as cursor,
    ):
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
) -> CommandHandler_T:
    @wraps(fn)
    async def wrapped_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = get_message(update)
        if not message:
            return

        command_name = sent_command(message)
        start_time = time.perf_counter()
        status = "completed"
        error: Exception | None = None

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

            if (
                command_name
                and message.from_user
                and await _is_blocked(message.from_user.id, command_name)
            ):
                status = "blocked"
                await message.reply_text("❌ You are blocked from using this command.")
                return

            schedule_background_task(set_command_reaction(), "command-reaction")

            await fn(update, context)
        except HandledCommandError as exc:
            status = "failed"
            error = exc
        except Exception as exc:
            status = "failed"
            error = exc
            try:
                await message.reply_text("Something went wrong. Please try again.")
            except TelegramError:
                logger.exception("Failed to send command error response")
            raise
        finally:
            if command_name and message.from_user:
                finish_command_event(
                    message,
                    command_name,
                    status,
                    start_time,
                    error,
                )

    return wrapped_command


def is_command_enabled(command: CommandFunc) -> bool:
    required_key = get_command_meta(command).api_key
    if not required_key:
        return True

    return bool(
        getattr(config.API, required_key, "")
        or getattr(config.TELEGRAM, required_key, "")
    )


async def usage_string(message: Message, func: CommandFunc) -> None:
    meta = get_command_meta(func)

    await message.reply_text(
        f"{meta.description}\n\n<b>Usage:</b>\n<pre>{meta.usage}</pre>\n\n<b>Example:</b>\n<pre>{meta.example}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
