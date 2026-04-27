import mimetypes

from telegram import Bot, Message


async def get_sticker_image_bytes(
    message: Message, bot: Bot
) -> tuple[bytes, str] | None:
    sticker = message.sticker
    if not sticker:
        return None

    if sticker.is_animated or sticker.is_video:
        # NOTE: Animated/video stickers aren't supported (we don't currently convert TGS/WEBM).
        # Keep behavior consistent with user-facing error messages in /ask and /edit.
        return None

    file = await bot.getFile(sticker.file_id)
    image_data = await file.download_as_bytearray()
    mime_type = (
        mimetypes.guess_type(file.file_path)[0] if file.file_path else None
    ) or "image/webp"
    return bytes(image_data), mime_type
