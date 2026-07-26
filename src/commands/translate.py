from telegram import Message, Update
from telegram.ext import ContextTypes

import commands
from utils.decorators import command
from utils.messages import get_message


async def text_grabber(
    message: Message, context: ContextTypes.DEFAULT_TYPE
) -> tuple[str, str] | None:
    if message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption
        return (text, context.args[0] if context.args else "en") if text else None
    if not context.args:
        return None
    if "-" not in context.args:
        return " ".join(context.args), "en"
    separator_index = context.args.index("-")
    text = " ".join(context.args[separator_index + 1 :])
    return (text, context.args[0]) if text else None


@command(
    triggers=["tl"],
    usage="/tl [language] - [content]",
    example="/tl fr - Good morning!",
    description="Translate a message or text to the desired language. "
    "Reply to a message with just the language code to translate it.",
)
async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    result = await text_grabber(message, context)
    if not result:
        await commands.usage_string(message, translate)
        return

    text, target_language = result
    from googletrans import Translator as GTranslator

    try:
        async with GTranslator() as translator:
            translated = await translator.translate(text, dest=target_language)
        await message.reply_text(translated.text)
    except ValueError:
        await message.reply_text(f"Invalid target language: {target_language}")
