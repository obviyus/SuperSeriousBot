import html
from typing import Any, Dict, List

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage

DICTIONARY_API_ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries/en_US/{}"


@triggers(["define", "d"])
@usage("/define [word]")
@description("Define a word.")
@example("/define posthumous")
async def define(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Define a word"""
    if not context.args:
        await commands.usage_string(update.message, define)
        return

    word = " ".join(context.args)
    definition = await _fetch_definition(word)

    if not definition:
        await update.message.reply_text(text="Word not found.")
        return

    formatted_definition = _format_definition(definition)
    await update.message.reply_text(
        text=formatted_definition,
        parse_mode=ParseMode.HTML,
    )


async def _fetch_definition(word: str) -> Dict[str, Any]:
    """Fetch word definition from the API"""
    async with aiohttp.ClientSession() as session:
        async with session.get(DICTIONARY_API_ENDPOINT.format(word)) as response:
            if response.status != 200:
                return {}
            data = await response.json()
            return data[0] if data else {}


def _format_definition(response: Dict[str, Any]) -> str:
    """Format the API response into a readable definition"""
    text = f'<b>{response["word"]}</b>'

    phonetics = _get_phonetics(response)
    if phonetics:
        text += f"\n🗣️ {phonetics}"

    meanings = response.get("meanings", [])
    if meanings:
        part_of_speech = meanings[0].get("partOfSpeech", "")
        definitions = meanings[0].get("definitions", [])
        if part_of_speech and definitions:
            text += f"\n\n<b>{part_of_speech}</b>"
            definition = definitions[0]
            text += f'\n  -  {html.escape(definition.get("definition", ""))}'

            synonyms = _get_synonyms(definition)
            if synonyms:
                text += "\n\nSynonyms:"
                for syn in synonyms[:2]:
                    text += f"\n  - {html.escape(syn)}"

    return text


def _get_phonetics(response: Dict[str, Any]) -> str:
    """Extract phonetics from the response"""
    phonetics = response.get("phonetics", [])
    return phonetics[0].get("text", "") if phonetics else ""


def _get_synonyms(definition: Dict[str, Any]) -> List[str]:
    """Extract synonyms from the definition"""
    return definition.get("synonyms", [])
