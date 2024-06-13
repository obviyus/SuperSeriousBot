from typing import Tuple

from deep_translator import GoogleTranslator
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from translatepy import Translator
from translatepy.exceptions import NoResult, UnknownLanguage

import commands
from utils.decorators import description, example, triggers, usage

translator = Translator()

supported_languages = {
    "af",
    "am",
    "ar",
    "az",
    "be",
    "bg",
    "bn",
    "bs",
    "ca",
    "ceb",
    "co",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "eo",
    "es",
    "et",
    "eu",
    "fa",
    "fi",
    "fr",
    "fy",
    "ga",
    "gd",
    "gl",
    "gu",
    "ha",
    "haw",
    "hi",
    "hmn",
    "hr",
    "ht",
    "hu",
    "hy",
    "id",
    "ig",
    "is",
    "it",
    "he",
    "ja",
    "jv",
    "ka",
    "kk",
    "km",
    "kn",
    "ko",
    "ku",
    "ky",
    "la",
    "lb",
    "lo",
    "lt",
    "lv",
    "mg",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "ne",
    "nl",
    "no",
    "ny",
    "or",
    "pa",
    "pl",
    "ps",
    "pt",
    "ro",
    "ru",
    "sd",
    "si",
    "sk",
    "sl",
    "sm",
    "sn",
    "so",
    "sq",
    "sr",
    "st",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "tl",
    "tr",
    "ug",
    "uk",
    "ur",
    "uz",
    "vi",
    "xh",
    "yi",
    "yo",
    "zh",
    "zu",
}


async def text_grabber(
    message: Message, context: ContextTypes.DEFAULT_TYPE
) -> Tuple[str, str] | None:
    text = None
    target_language = "en"

    if message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption
        if context.args:
            target_language = (
                context.args[0] if context.args[0] in supported_languages else "en"
            )
    else:
        if context.args:
            if "-" in context.args:
                separator_index = context.args.index("-")
                target_language = (
                    context.args[0] if context.args[0] in supported_languages else "en"
                )
                text = " ".join(context.args[separator_index + 1 :])
            else:
                text = " ".join(context.args)

    if not text:
        return None

    return text, target_language


async def translate_and_reply(
    message: Message, text: str, target_language: str
) -> None:
    translated = GoogleTranslator(source="auto", target=target_language).translate(text)
    await message.reply_text(
        translated,
    )


@triggers(["tl"])
@example("/tl fr - Good morning!")
@usage("/tl [language] - [content]")
@description(
    "Translate a message or text to the desired language. "
    "Reply to a message with just the language code to translate it."
)
async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Translate a message.
    """
    result = await text_grabber(update.message, context)
    if not result:
        await commands.usage_string(update.message, translate)
        return

    await translate_and_reply(update.message, result[0], result[1])


@triggers(["tts"])
@example("/tts fr - Good morning!")
@usage("/tts [language] - [content]")
@description(
    "Generate text-to-speech of message in the desired speaker language. "
    "Reply to a message with just the language code to TTS it."
)
async def tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Transcribe a message and send it as a voice message.
    """
    result = await text_grabber(update.message, context)
    if not result:
        await commands.usage_string(update.message, tts)
        return

    try:
        await update.message.reply_voice(
            translator.text_to_speech(result[0], source_language=result[1]).result,
        )
    except UnknownLanguage as e:
        await update.message.reply_text(
            f"Couldn't recognize the given language: <b>{result[1]}</b>. "
            f"Did you mean: {e.guessed_language[:2]} ({e.guessed_language})? <b>Similarity: {e.similarity:.2f}%</b>",
            parse_mode=ParseMode.HTML,
        )
    except NoResult:
        await update.message.reply_text("No service returned a valid result.")
