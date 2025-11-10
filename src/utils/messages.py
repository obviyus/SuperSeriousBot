from telegram import Message, Update


def get_message(update: Update) -> Message | None:
    """Return the message attached to an update, or None if absent."""
    return update.message
