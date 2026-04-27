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
    if not data:
        await message.reply_text(text="Word not found.")
        return

    definition = data[0]
    text = f"<b>{definition['word']}</b>"
    phonetics = definition.get("phonetics", [])
    if phonetics and phonetics[0].get("text"):
        text += f"\n🗣️ {phonetics[0]['text']}"

    meanings = definition.get("meanings", [])
    if meanings:
        part_of_speech = meanings[0].get("partOfSpeech", "")
        definitions = meanings[0].get("definitions", [])
        if part_of_speech and definitions:
            text += f"\n\n<b>{part_of_speech}</b>"
            first_definition = definitions[0]
            text += f"\n  -  {html.escape(first_definition.get('definition', ''))}"
            synonyms = first_definition.get("synonyms", [])
            if synonyms:
                text += "\n\nSynonyms:"
                for syn in synonyms[:2]:
                    text += f"\n  - {html.escape(syn)}"

    await message.reply_text(text=text, parse_mode=ParseMode.HTML)
