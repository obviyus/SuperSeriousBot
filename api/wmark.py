from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageFont, ImageDraw

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def wmark(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Add watermark to an image"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    if not (message.reply_to_message and message.reply_to_message.photo and context.args):
        message.reply_text(
            text="*Usage:* \nReply to a photo with `/wmark {watermark text}|{COLOR}`\n"
                 "*Example:* `/wmark @channelname|#AA33FF`\n"
                 "                 `/wmark @channelname2`\n"
                 "Color is optional and you can specify a hex color value. Defaults to white."
        )
    else:
        pic: telegram.PhotoSize = message.reply_to_message.photo[-1]
        h: int = pic.height
        w: int = pic.width

        args: list = ''.join(context.args).split("|")

        watermark_text: str = args[0]
        if len(args) == 2 and args[1]:
            color: str = args[1]
        else:
            color: str = 'white'

        with BytesIO(pic.get_file().download_as_bytearray()) as pic_file, BytesIO() as wimage:
            try:
                image = Image.open(pic_file)
                draw = ImageDraw.Draw(image)

                font = ImageFont.truetype("files/liberation.ttf", size=int(h / 30))

                draw.text((w, h), watermark_text, fill=color, font=font, anchor="rb")

                image.save(wimage, 'JPEG')
                wimage.seek(0)

                message.reply_photo(photo=wimage)
            except ValueError:
                message.reply_text(text="Invalid color")
