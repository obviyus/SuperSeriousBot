from urllib.parse import urlencode


def make(update, context):
    """Generate QR code from given data"""
    message = update.message
    data = ' '.join(context.args)

    if not data:
        message.reply_text(
            text="*Usage:* `/qr {CONTENT}`\n"
                 "*Example:* `/qr superserio.us`"
        )

    else:
        payload = {'data': data}
        result = "https://api.qrserver.com/v1/create-qr-code?" + urlencode(payload)
        message.reply_photo(
            photo=result,
        )
