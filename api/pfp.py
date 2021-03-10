from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageOps

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def pad_image(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Pad images to 1:1 for use in profile pictures"""

    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    if not (message.reply_to_message and message.reply_to_message.photo):
        message.reply_text(
            text="*Usage:* \nReply to a photo with `/pfp {COLOR}`\n"
                 "*Example:* `/pfp red`\n"
                 "Defaults to black if none provided"
        )
    else:
        pic = message.reply_to_message.photo[-1]
        size = (max(pic.width, pic.height), max(pic.width, pic.height))
        color = ''.join(context.args) or 'black'

        with BytesIO(pic.get_file().download_as_bytearray()) as pic_file, BytesIO() as dp:
            try:
                padded_image = ImageOps.pad(
                    image=Image.open(pic_file), size=size, color=color
                )
                padded_image.save(dp, 'JPEG')

                dp.seek(0)
                message.reply_photo(photo=dp)
            except ValueError:
                message.reply_text(text="Invalid color")
