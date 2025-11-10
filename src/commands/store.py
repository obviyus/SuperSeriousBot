import enum

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


class FileType(enum.Enum):
    """File type enum."""

    DOCUMENT = "DOCUMENT"
    PHOTO = "PHOTO"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    ANIMATION = "ANIMATION"
    VOICE = "VOICE"
    STICKER = "STICKER"
    VIDEO_NOTE = "VIDEO_NOTE"
    UNKNOWN = "UNKNOWN"


@triggers(["set"])
@usage("/set [key]")
@example("/set rickroll")
@description("Reply to a media object to store it with a key. Get it back with /get.")
async def set_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Save a media object."""
    if not message.from_user:
        return

    if not message.reply_to_message:
        await commands.usage_string(message, set_object)
        return

    file_id, file_unique_id, file_type = None, None, None
    reply = message.reply_to_message

    if reply.document:
        file_id, file_unique_id, file_type = (
            reply.document.file_id,
            reply.document.file_unique_id,
            FileType.DOCUMENT,
        )
    elif reply.photo:
        file_id, file_unique_id, file_type = (
            reply.photo[-1].file_id,
            reply.photo[-1].file_unique_id,
            FileType.PHOTO,
        )
    elif reply.audio:
        file_id, file_unique_id, file_type = (
            reply.audio.file_id,
            reply.audio.file_unique_id,
            FileType.AUDIO,
        )
    elif reply.video:
        file_id, file_unique_id, file_type = (
            reply.video.file_id,
            reply.video.file_unique_id,
            FileType.VIDEO,
        )
    elif reply.animation:
        file_id, file_unique_id, file_type = (
            reply.animation.file_id,
            reply.animation.file_unique_id,
            FileType.ANIMATION,
        )
    elif reply.voice:
        file_id, file_unique_id, file_type = (
            reply.voice.file_id,
            reply.voice.file_unique_id,
            FileType.VOICE,
        )
    elif reply.sticker:
        file_id, file_unique_id, file_type = (
            reply.sticker.file_id,
            reply.sticker.file_unique_id,
            FileType.STICKER,
        )
    elif reply.video_note:
        file_id, file_unique_id, file_type = (
            reply.video_note.file_id,
            reply.video_note.file_unique_id,
            FileType.VIDEO_NOTE,
        )
    else:
        await message.reply_text("Could not find a media object in the message.")
        return

    if not context.args:
        await message.reply_to_message.reply_text(
            "Please specify a key name for the object."
        )
        return

    key = context.args[0]

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM object_store WHERE key = ?;
            """,
            (key,),
        ) as cursor:
            if await cursor.fetchone():
                await message.reply_text(
                    f"Object with key <code>{key}</code> already exists.",
                    parse_mode=ParseMode.HTML,
                )
                return

        async with conn.execute(
            """
            SELECT * FROM object_store WHERE file_unique_id = ?;
            """,
            (file_unique_id,),
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                await message.reply_text(
                    f"""This file has already been stored with key <code>{result["key"]}</code>.""",
                    parse_mode=ParseMode.HTML,
                )
                return

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            INSERT INTO object_store (key, file_id, file_unique_id, user_id, type) VALUES (?, ?, ?, ?, ?);
            """,
            (
                key,
                file_id,
                file_unique_id,
                message.from_user.id,
                file_type.value,
            ),
        )
        await conn.commit()

    await message.reply_text(
        f"Object with key <code>{key}</code> saved. You can get it by using <code>/get {key}</code>.",
        parse_mode=ParseMode.HTML,
    )


@triggers(["get"])
@usage("/get [key]")
@example("/get rickroll")
@description("Get an object from the store.")
async def get_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Get a media object."""
    if not context.args:
        await commands.usage_string(message, get_object)
        return

    key = context.args[0]

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM object_store WHERE key = ? COLLATE NOCASE;
            """,
            (key,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await message.reply_text(
                f"Object with key <code>{key}</code> does not exist.",
                parse_mode=ParseMode.HTML,
            )
            return

        file_id, file_type = row["file_id"], row["type"]

        # Helper function to send media
        async def send_media(message, file_type, file_id):
            send_functions = {
                FileType.DOCUMENT: "reply_document",
                FileType.PHOTO: "reply_photo",
                FileType.AUDIO: "reply_audio",
                FileType.VIDEO: "reply_video",
                FileType.ANIMATION: "reply_animation",
                FileType.VOICE: "reply_voice",
                FileType.STICKER: "reply_sticker",
                FileType.VIDEO_NOTE: "reply_video_note",
            }
            method_name = send_functions.get(FileType(file_type))
            if method_name:
                method = getattr(message, method_name)
                await method(**{FileType(file_type).name.lower(): file_id})
            else:
                await message.reply_text(
                    f"Object with key <code>{key}</code> is of unknown type.",
                    parse_mode=ParseMode.HTML,
                )

        target_message = message.reply_to_message or message
        await send_media(target_message, file_type, file_id)

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            UPDATE object_store SET fetch_count = fetch_count + 1 WHERE key = ?;
            """,
            (key,),
        )
        await conn.commit()
