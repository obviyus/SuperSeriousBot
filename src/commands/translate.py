import difflib
import io

import gtts.lang
from googletrans import Translator as GTranslator
from gtts import gTTS
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage


async def text_grabber(
    message: Message, context: ContextTypes.DEFAULT_TYPE
) -> tuple[str, str] | None:
    text = None
    target_language = "en"

    if message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption
        if context.args:
            target_language = context.args[0]
    else:
        if context.args:
            if "-" in context.args:
                separator_index = context.args.index("-")
                target_language = context.args[0]
                text = " ".join(context.args[separator_index + 1 :])
            else:
                text = " ".join(context.args)

    if not text:
        return None

    return text, target_language


async def translate_and_reply(
    message: Message, text: str, target_language: str
) -> None:
    try:
        async with GTranslator() as translator:
            translated = await translator.translate(text, dest=target_language)
        await message.reply_text(
            translated.text,
        )
    except ValueError:
        await message.reply_text(f"Invalid target language: {target_language}")


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

    text, lang = result
    langs = gtts.lang.tts_langs()
    if lang.lower() not in langs:
        closest = difflib.get_close_matches(
            lang.lower(), list(langs.keys()), n=1, cutoff=0.5
        )
        if closest:
            sim = difflib.SequenceMatcher(None, lang.lower(), closest[0]).ratio() * 100
            await update.message.reply_text(
                f"Couldn't recognize the given language: <b>{lang}</b>. "
                f"Did you mean: {closest[0]} ({langs[closest[0]]})? <b>Similarity: {sim:.2f}%</b>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(f"Invalid language: <b>{lang}</b>")
        return

    try:
        tts_obj = gTTS(text, lang=lang.lower())
        fp = io.BytesIO()
        tts_obj.write_to_fp(fp)
        fp.seek(0)
        await update.message.reply_voice(fp)
    except Exception as e:
        await update.message.reply_text(f"Error: {e!s}")
