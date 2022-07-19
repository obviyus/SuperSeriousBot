from telegram import Update
from telegram.ext import ContextTypes
from translatepy import Translator

import utils

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


async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Translate a message.
    """

    text = (
        update.message.reply_to_message.text or update.message.reply_to_message.caption
    )

    target_language = "en"
    if len(context.args) > 0 and context.args[0] in supported_languages:
        target_language = context.args[0]

    if text:
        await update.message.reply_text(
            translator.translate(text, target_language).result,
        )
        return

    if context.args[1:2] == ["-"]:
        target_language = context.args[0]
        text = " ".join(context.args[2:])
    else:
        text = " ".join(context.args)

    if not text:
        await utils.usage_string(update.message)
        return

    await update.message.reply_text(
        translator.translate(text, target_language).result,
    )


async def tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Translate a message and send it as a voice message.
    """

    text = (
        update.message.reply_to_message.text or update.message.reply_to_message.caption
    )

    target_language = "auto"
    if len(context.args) > 0 and context.args[0] in supported_languages:
        target_language = context.args[0]

    if text:
        await update.message.reply_voice(
            translator.text_to_speech(text, source_language=target_language).result,
        )
        return

    if context.args[1:2] == ["-"]:
        target_language = context.args[0]
        text = " ".join(context.args[2:])
    else:
        text = " ".join(context.args)

    if not text:
        await utils.usage_string(update.message)
        return

    await update.message.reply_voice(
        translator.text_to_speech(text, source_language=target_language).result,
    )