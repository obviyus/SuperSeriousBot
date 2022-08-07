import html

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage

DICTIONARY_API_ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries"


@triggers(["define"])
@usage("/define [word]")
@description("Define a word.")
@example("/define posthumous")
async def define(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Define a word"""
    lang: str = "en_US"

    if not context.args:
        await commands.usage_string(update.message, define)
        return

    if len(context.args) < 2:
        word = context.args[0]
    else:
        if context.args[1:2] == ["-"]:
            lang = context.args[0]
        word = context.args[2]

    async with httpx.AsyncClient() as client:
        response = await client.get(DICTIONARY_API_ENDPOINT + f"/{lang}/{word}")

    if response.status_code != 200:
        await update.message.reply_text(text="Word not found.")
        return

    response = response.json()[0]
    text = f'<b>{response["word"]}</b>'
    if "text" in response["phonetics"][0]:
        text += f'\n🗣️ {response["phonetics"][0]["text"]}'

    text += f"\n" f'\n<b>{response["meanings"][0]["partOfSpeech"]}</b>'
    definition = response["meanings"][0]["definitions"][0]
    text += f'\n  -  {html.escape(definition["definition"])}'

    if "synonyms" in definition and len(definition["synonyms"]) > 0:
        text += f"\n\nSynonyms:"
        for syn in definition["synonyms"][:2]:
            text += f"\n  - {html.escape(syn)}"

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
    )
