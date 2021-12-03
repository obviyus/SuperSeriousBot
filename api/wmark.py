from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageFont, ImageDraw, ImageColor

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

        args: list = ' '.join(context.args).split("|")

        watermark_text: str = args[0]
        if len(args) == 2 and args[1]:
            color: str = args[1].strip()
            stroke_width: int = 0
        else:
            color: str = 'white'
            stroke_width: int = 1

        color_tup: tuple = ImageColor.getrgb(color)
        color_tup = (*color_tup, 150)

        with BytesIO(pic.get_file().download_as_bytearray()) as pic_file, BytesIO() as wimage:
            try:
                base_image = Image.open(pic_file).convert("RGBA")
                txt_layer = Image.new("RGBA", base_image.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(txt_layer)

                if w > h:
                    font = ImageFont.truetype("files/liberation.ttf", size=int(h / 12))
                    draw.text(
                        (w / 2, h - 20),
                        watermark_text,
                        fill=color_tup,
                        font=font,
                        anchor="md",
                        stroke_width=stroke_width,
                        stroke_fill="black",
                    )
                else:
                    font = ImageFont.truetype("files/liberation.ttf", size=int(w / 20))
                    draw.text(
                        (w / 2, (h / 2) - 20),
                        watermark_text,
                        fill=color_tup,
                        font=font,
                        anchor="md",
                        stroke_width=stroke_width,
                        stroke_fill="black",
                    )
                    txt_layer = txt_layer.rotate(90, center=(w / 2, h / 2), translate=(w / 2, 0))

                out_image = Image.alpha_composite(base_image, txt_layer)

                out_image.save(wimage, 'PNG')
                wimage.seek(0)

                message.reply_photo(photo=wimage)
            except ValueError:
                message.reply_text(text="Invalid color")
