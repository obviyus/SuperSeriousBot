import mimetypes

from telegram import Bot, Message


async def get_sticker_image_bytes(
    message: Message, bot: Bot
) -> tuple[bytes, str] | None:
    sticker = message.sticker
    if not sticker:
        return None

    if sticker.is_animated or sticker.is_video:
        return None

    file = await bot.getFile(sticker.file_id)
    image_data = await file.download_as_bytearray()
    mime_type = (
        mimetypes.guess_type(file.file_path)[0] if file.file_path else None
    ) or "image/webp"
    return bytes(image_data), mime_type


async def get_message_image_bytes(
    message: Message,
    bot: Bot,
    *,
    allow_document: bool = False,
) -> tuple[bytes, str | None] | None:
    if message.photo:
        photo = message.photo[-1]
        file = await bot.getFile(photo.file_id)
        return bytes(await file.download_as_bytearray()), mimetypes.guess_type(
            file.file_path or ""
        )[0]
    if message.sticker:
        sticker_payload = await get_sticker_image_bytes(message, bot)
        if not sticker_payload:
            raise ValueError(
                "Animated/video stickers aren't supported yet. Send a static sticker or image."
            )
        return sticker_payload
    if (
        allow_document
        and message.document
        and (message.document.mime_type or "").startswith("image/")
    ):
        file = await bot.getFile(message.document.file_id)
        return bytes(await file.download_as_bytearray()), (
            message.document.mime_type or mimetypes.guess_type(file.file_path or "")[0]
        )
    return None
