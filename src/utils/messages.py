import io

from telegram import InlineKeyboardMarkup, Message, Update
from telegram.ext import ExtBot


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


async def reply_markdown_or_plain(
    message: Message,
    text: str,
    *,
    disable_web_page_preview: bool = False,
    document_name: str | None = None,
):
    import telegramify_markdown

    try:
        formatted = telegramify_markdown.markdownify(text)
        if len(formatted) <= 4096:
            return await message.reply_text(
                formatted,
                disable_web_page_preview=disable_web_page_preview,
                parse_mode="MarkdownV2",
            )
    except Exception:
        pass

    if len(text) <= 4096 or not document_name:
        return await message.reply_text(
            text,
            disable_web_page_preview=disable_web_page_preview,
        )

    buffer = io.BytesIO(text.encode())
    buffer.name = document_name
    return await message.reply_document(buffer)


async def send_markdown_or_plain(
    bot: ExtBot,
    chat_id: int,
    text: str,
    *,
    disable_web_page_preview: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    import telegramify_markdown

    try:
        formatted = telegramify_markdown.markdownify(text)
        if len(formatted) <= 4096:
            return await bot.send_message(
                chat_id=chat_id,
                text=formatted,
                disable_web_page_preview=disable_web_page_preview,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )
    except Exception:
        pass

    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        disable_web_page_preview=disable_web_page_preview,
        reply_markup=reply_markup,
    )
