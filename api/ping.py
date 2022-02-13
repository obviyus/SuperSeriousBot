from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def ping(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Simple response time measurement"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    message.reply_text(
        text=f"pong ({(datetime.now().timestamp() - message.date.timestamp()) * 1000:.2f} ms)",
    )
