import mimetypes

from telegram import Bot, Message


async def _download_file_bytes(
    bot: Bot, file_id: str, fallback_mime_type: str
) -> tuple[bytes, str]:
    file = await bot.getFile(file_id)
    image_data = await file.download_as_bytearray()
    mime_type = (
        mimetypes.guess_type(file.file_path)[0] if file.file_path else None
    ) or fallback_mime_type
    return bytes(image_data), mime_type


async def get_sticker_image_bytes(
    message: Message, bot: Bot
) -> tuple[bytes, str] | None:
    sticker = message.sticker
    if not sticker:
        return None

    if sticker.is_animated or sticker.is_video:
        # AIDEV-NOTE: Animated/video stickers use thumbnail fallback; full conversion not supported.
        if not sticker.thumbnail:
            return None
        return await _download_file_bytes(
            bot, sticker.thumbnail.file_id, "image/jpeg"
        )

    return await _download_file_bytes(bot, sticker.file_id, "image/webp")
