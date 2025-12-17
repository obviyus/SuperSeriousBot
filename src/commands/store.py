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


# Mapping of FileType to the method name used to send it
MEDIA_SEND_METHODS = {
    FileType.DOCUMENT: "reply_document",
    FileType.PHOTO: "reply_photo",
    FileType.AUDIO: "reply_audio",
    FileType.VIDEO: "reply_video",
    FileType.ANIMATION: "reply_animation",
    FileType.VOICE: "reply_voice",
    FileType.STICKER: "reply_sticker",
    FileType.VIDEO_NOTE: "reply_video_note",
}


def extract_media_info(message) -> tuple[str | None, str | None, FileType | None]:
    """Extract file_id, file_unique_id, and FileType from a message."""
    # Priority order for checking media types
    media_types = [
        ("document", FileType.DOCUMENT),
        ("photo", FileType.PHOTO),
        ("audio", FileType.AUDIO),
        ("video", FileType.VIDEO),
        ("animation", FileType.ANIMATION),
        ("voice", FileType.VOICE),
        ("sticker", FileType.STICKER),
        ("video_note", FileType.VIDEO_NOTE),
    ]

    for attr, file_type in media_types:
        media_obj = getattr(message, attr, None)
        if media_obj:
            if attr == "photo":
                # Photos are a list, take the last (highest quality) one
                return media_obj[-1].file_id, media_obj[-1].file_unique_id, file_type
            return media_obj.file_id, media_obj.file_unique_id, file_type

    return None, None, None


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

    file_id, file_unique_id, file_type = extract_media_info(message.reply_to_message)

    if not file_id or not file_type:
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

        file_id, file_type_str = row["file_id"], row["type"]

        try:
            file_type = FileType(file_type_str)
            method_name = MEDIA_SEND_METHODS.get(file_type)

            if method_name:
                target_message = message.reply_to_message or message
                method = getattr(target_message, method_name)
                # Construct the kwargs: e.g. reply_photo(photo=file_id)
                # The argument name is usually the lowercase enum name (photo, audio, etc.)
                # Exception: video_note is passed as video_note, which matches enum name
                arg_name = file_type.name.lower()
                await method(**{arg_name: file_id})
            else:
                raise ValueError("Unknown media type method")

        except (ValueError, AttributeError):
            await message.reply_text(
                f"Object with key <code>{key}</code> has an invalid or unsupported type.",
                parse_mode=ParseMode.HTML,
            )

    async with get_db(write=True) as conn:
        await conn.execute(
            """
            UPDATE object_store SET fetch_count = fetch_count + 1 WHERE key = ?;
            """,
            (key,),
        )
        await conn.commit()
