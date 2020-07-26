def make(update, context):
    """ Command to generate QR code from given data"""
    message = update.message
    data = ' '.join(context.args)

    if not data:
        message.reply_text(
            text="*Usage:* `/qr {CONTENT}`\n"
                 "*Example:* `/qr superserio.us`"
        )

    else:
        message.reply_photo(
            photo=f'https://api.qrserver.com/v1/create-qr-code/?data={data}',
        )
