from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import get_db
from utils.decorators import command
from utils.messages import get_message



@command(
    triggers=["set"],
    usage="/set [key]",
    example="/set rickroll",
    description="Reply to a media object to store it with a key. Get it back with /get.",
)
async def set_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return

    if not message.reply_to_message:
        await commands.usage_string(message, set_object)
        return

    file_id = file_unique_id = file_type = None
    for attr in (
        "document",
        "photo",
        "audio",
        "video",
        "animation",
        "voice",
        "sticker",
        "video_note",
    ):
        media = getattr(message.reply_to_message, attr, None)
        if media:
            picked_media = media[-1] if attr == "photo" else media
            file_id = picked_media.file_id
            file_unique_id = picked_media.file_unique_id
            file_type = attr.upper()
            break
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
            "SELECT * FROM object_store WHERE key = ?;",
            (key,),
        ) as cursor:
            if await cursor.fetchone():
                await message.reply_text(
                    f"Object with key <code>{key}</code> already exists.",
                    parse_mode=ParseMode.HTML,
                )
                return

        async with conn.execute(
            "SELECT * FROM object_store WHERE file_unique_id = ?;",
            (file_unique_id,),
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                await message.reply_text(
                    f"This file has already been stored with key <code>{result['key']}</code>.",
                    parse_mode=ParseMode.HTML,
                )
                return

        await conn.execute(
            """
            INSERT INTO object_store (key, file_id, file_unique_id, user_id, type) VALUES (?, ?, ?, ?, ?);
            """,
            (key, file_id, file_unique_id, message.from_user.id, file_type),
        )

    await message.reply_text(
        f"Object with key <code>{key}</code> saved. You can get it by using <code>/get {key}</code>.",
        parse_mode=ParseMode.HTML,
    )


@command(
    triggers=["get"],
    usage="/get [key]",
    example="/get rickroll",
    description="Get an object from the store.",
)
async def get_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not context.args:
        await commands.usage_string(message, get_object)
        return

    key = context.args[0]

    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM object_store WHERE key = ? COLLATE NOCASE;",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await message.reply_text(
                f"Object with key <code>{key}</code> does not exist.",
                parse_mode=ParseMode.HTML,
            )
            return

        file_id = row["file_id"]
        method_name = f"reply_{row['type'].lower()}"

        try:
            target_message = message.reply_to_message or message
            await getattr(target_message, method_name)(**{row['type'].lower(): file_id})
        except AttributeError:
            await message.reply_text(
                f"Object with key <code>{key}</code> has an invalid or unsupported type.",
                parse_mode=ParseMode.HTML,
            )

        await conn.execute(
            "UPDATE object_store SET fetch_count = fetch_count + 1 WHERE key = ?;",
            (key,),
        )
