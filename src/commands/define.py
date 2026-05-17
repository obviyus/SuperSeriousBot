import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from utils.decorators import command
from utils.messages import get_message

DICTIONARY_API_ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries/en_US/{}"


@command(
    triggers=["define", "d"],
    usage="/define [word]",
    example="/define posthumous",
    description="Define a word.",
)
async def define(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not context.args:
        await commands.usage_string(message, define)
        return

    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(
            DICTIONARY_API_ENDPOINT.format(" ".join(context.args))
        ) as response:
            if response.status != 200:
                await message.reply_text(text="Word not found.")
                return
            data = await response.json()
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        await message.reply_text(text="Word not found.")
        return

    definition = data[0]
    word = definition.get("word")
    if not isinstance(word, str):
        await message.reply_text(text="Word not found.")
        return

    text = f"<b>{html.escape(word)}</b>"
    phonetics = definition.get("phonetics", [])
    first_phonetic = phonetics[0] if isinstance(phonetics, list) and phonetics else None
    if isinstance(first_phonetic, dict) and isinstance(first_phonetic.get("text"), str):
        text += f"\n🗣️ {html.escape(first_phonetic['text'])}"

    meanings = definition.get("meanings", [])
    first_meaning = meanings[0] if isinstance(meanings, list) and meanings else None
    if isinstance(first_meaning, dict):
        part_of_speech = first_meaning.get("partOfSpeech", "")
        definitions = first_meaning.get("definitions", [])
        if isinstance(part_of_speech, str) and isinstance(definitions, list) and definitions:
            text += f"\n\n<b>{html.escape(part_of_speech)}</b>"
            first_definition = definitions[0]
            if not isinstance(first_definition, dict):
                await message.reply_text(text="Word not found.")
                return
            first_definition_text = first_definition.get("definition", "")
            if not isinstance(first_definition_text, str):
                await message.reply_text(text="Word not found.")
                return
            text += f"\n  -  {html.escape(first_definition_text)}"
            synonyms = first_definition.get("synonyms", [])
            if isinstance(synonyms, list) and synonyms:
                text += "\n\nSynonyms:"
                for syn in synonyms[:2]:
                    if isinstance(syn, str):
                        text += f"\n  - {html.escape(syn)}"

    await message.reply_text(text=text, parse_mode=ParseMode.HTML)
