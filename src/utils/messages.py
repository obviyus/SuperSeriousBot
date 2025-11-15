from telegram import Message, Update


def get_message(update: Update) -> Message | None:
    """Return the message attached to an update, or None if absent."""
    if isinstance(update.message, Message):
        return update.message

    if isinstance(update.effective_message, Message):
        return update.effective_message

    if update.callback_query and isinstance(update.callback_query.message, Message):
        return update.callback_query.message

    return None
