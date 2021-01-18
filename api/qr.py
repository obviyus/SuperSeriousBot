from urllib.parse import urlencode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram


def make(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Generate QR code from given data"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return
    data: str = ' '.join(context.args) if context.args else ''

    if not data:
        message.reply_text(
            text="*Usage:* `/qr {CONTENT}`\n"
                 "*Example:* `/qr superserio.us`"
        )

    else:
        result: str = "https://api.qrserver.com/v1/create-qr-code?" + urlencode({'data': data})
        message.reply_photo(photo=result)
