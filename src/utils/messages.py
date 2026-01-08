from telegram import Message, Update


def get_message(update: Update) -> Message | None:
    """Return the message attached to an update, or None if absent."""
    candidates = (
        update.message,
        update.effective_message,
        update.callback_query.message if update.callback_query else None,
    )
    for candidate in candidates:
        if isinstance(candidate, Message):
            return candidate

    return None
