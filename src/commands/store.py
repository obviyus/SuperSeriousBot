import enum

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


class FileType(enum.Enum):
    """File type enum."""

    DOCUMENT = "DOCUMENT"
    PHOTO = "PHOTO"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    ANIMATION = "ANIMATION"
    VOICE = "VOICE"
    STICKER = "STICKER"
    UNKNOWN = "UNKNOWN"


@triggers(["set"])
@usage("/set [key]")
@example("/set rickroll")
@description("Reply to a media object to store it with a key. Get it back with /get.")
async def set_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save a media object."""
    if not update.message.reply_to_message:
        await commands.usage_string(update.message, set_object)
        return

    if update.message.reply_to_message.document:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.document.file_id,
            update.message.reply_to_message.document.file_unique_id,
            FileType.DOCUMENT,
        )
    elif update.message.reply_to_message.photo:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.photo[-1].file_id,
            update.message.reply_to_message.photo[-1].file_unique_id,
            FileType.PHOTO,
        )
    elif update.message.reply_to_message.audio:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.audio.file_id,
            update.message.reply_to_message.audio.file_unique_id,
            FileType.AUDIO,
        )
    elif update.message.reply_to_message.video:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.video.file_id,
            update.message.reply_to_message.video.file_unique_id,
            FileType.VIDEO,
        )
    elif update.message.reply_to_message.animation:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.animation.file_id,
            update.message.reply_to_message.animation.file_unique_id,
            FileType.ANIMATION,
        )
    elif update.message.reply_to_message.voice:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.voice.file_id,
            update.message.reply_to_message.voice.file_unique_id,
            FileType.VOICE,
        )
    elif update.message.reply_to_message.sticker:
        file_id, file_unique_id, file_type = (
            update.message.reply_to_message.sticker.file_id,
            update.message.reply_to_message.sticker.file_unique_id,
            FileType.STICKER,
        )
    else:
        await update.message.reply_text("Could not find a media object in the message.")
        return

    if not context.args:
        await update.message.reply_to_message.reply_text(
            "Please specify a key name for the object."
        )
        return

    key = context.args[0]

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM object_store WHERE key = ?;
        """,
        (key,),
    )

    if cursor.fetchone():
        await update.message.reply_text(
            f"Object with key <code>{key}</code> already exists.",
            parse_mode=ParseMode.HTML,
        )
        return

    cursor.execute(
        """
        SELECT * FROM object_store WHERE file_unique_id = ?;
        """,
        (file_unique_id,),
    )

    result = cursor.fetchone()
    if result:
        await update.message.reply_text(
            f"""This file has already been stored with key <code>{result["key"]}</code>.""",
            parse_mode=ParseMode.HTML,
        )
        return

    cursor.execute(
        """
        INSERT INTO object_store (key, file_id, file_unique_id, user_id, type) VALUES (?, ?, ?, ?, ?);
        """,
        (key, file_id, file_unique_id, update.message.from_user.id, file_type.value),
    )

    await update.message.reply_text(
        f"Object with key <code>{key}</code> saved. You can get it by using <code>/get {key}</code>.",
        parse_mode=ParseMode.HTML,
    )


@triggers(["get"])
@usage("/get [key]")
@example("/get rickroll")
@description("Get an object from the store.")
async def get_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a media object."""
    if not context.args:
        await commands.usage_string(update.message, get_object)
        return

    key = context.args[0]

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM object_store WHERE key = ? COLLATE NOCASE;
        """,
        (key,),
    )

    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(
            f"Object with key <code>{key}</code> does not exist.",
            parse_mode=ParseMode.HTML,
        )
        return

    file_id, user_id, file_type = row["file_id"], row["user_id"], row["type"]

    # TODO: Refactor into a generic function.
    if update.message.reply_to_message:
        await update.message.delete()
        match FileType(file_type):
            case FileType.DOCUMENT:
                await update.message.reply_to_message.reply_document(
                    document=file_id,
                )
            case FileType.PHOTO:
                await update.message.reply_to_message.reply_photo(
                    photo=file_id,
                )
            case FileType.AUDIO:
                await update.message.reply_to_message.reply_audio(
                    audio=file_id,
                )
            case FileType.VIDEO:
                await update.message.reply_to_message.reply_video(
                    video=file_id,
                )
            case FileType.ANIMATION:
                await update.message.reply_to_message.reply_animation(
                    animation=file_id,
                )
            case FileType.VOICE:
                await update.message.reply_to_message.reply_voice(
                    voice=file_id,
                )
            case FileType.STICKER:
                await update.message.reply_to_message.reply_sticker(
                    sticker=file_id,
                )
            case FileType.UNKNOWN:
                await update.message.reply_to_message.reply_text(
                    f"Object with key <code>{key}</code> is of unknown type.",
                    parse_mode=ParseMode.HTML,
                )
                return
    else:
        match FileType(file_type):
            case FileType.DOCUMENT:
                await update.message.reply_document(
                    document=file_id,
                )
            case FileType.PHOTO:
                await update.message.reply_photo(
                    photo=file_id,
                )
            case FileType.AUDIO:
                await update.message.reply_audio(
                    audio=file_id,
                )
            case FileType.VIDEO:
                await update.message.reply_video(
                    video=file_id,
                )
            case FileType.ANIMATION:
                await update.message.reply_animation(
                    animation=file_id,
                )
            case FileType.VOICE:
                await update.message.reply_voice(
                    voice=file_id,
                )
            case FileType.STICKER:
                await update.message.reply_sticker(
                    sticker=file_id,
                )
            case FileType.UNKNOWN:
                await update.message.reply_text(
                    f"Object with key <code>{key}</code> is of unknown type.",
                    parse_mode=ParseMode.HTML,
                )
                return
