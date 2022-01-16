from io import BytesIO
from typing import TYPE_CHECKING

import requests
from pydub import AudioSegment

if TYPE_CHECKING:
    import telegram
    import telegram.ext

DICTIONARY_API_ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries"


def define(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Define a word"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    text: str
    lang: str = "en_US"

    if not context.args:
        message.reply_text(
            "*Usage:* `/d {LANG} - {SENTENCE}`\n"
            "*Example:* `/d fr - bonjour`\n"
            "Defaults to `en_US` if none provided.\n"
        )
        return
    else:
        if len(context.args) < 2:
            word = context.args[0]
        else:
            if context.args[1:2] == ["-"]:
                lang = context.args[0]
            word = context.args[2]

        response = requests.get(DICTIONARY_API_ENDPOINT + f"/{lang}/{word}")
        if response.status_code != 200:
            message.reply_text(text="Word not found.")
            return
        response = response.json()[0]

        text = f'*{response["word"]}*'
        if "text" in response["phonetics"][0]:
            text += f'\n🗣️ {response["phonetics"][0]["text"]}'
        text += f"\n" f'\n*{response["meanings"][0]["partOfSpeech"]}*'

        definition = response["meanings"][0]["definitions"][0]
        text += f'\n  -  {definition["definition"]}'
        if "synonyms" in definition:
            text += f"\n\nSynonyms:"
            for syn in definition["synonyms"][:2]:
                text += f"\n  - {syn}"

        # A raw MP3 is sent as a document, converting to OGG fixes that and sends as a playable audio file
        if "audio" in response["phonetics"][0]:
            url: str = response["phonetics"][0]["audio"]
            if url.startswith("//ssl"):
                url = "http:" + url

            data = requests.get(url)
            data = BytesIO(data.content)

            audio = AudioSegment.from_mp3(data)
            with BytesIO() as buf:
                audio.export(buf, format="ogg", codec="libopus")
                buf.seek(0)

                message.reply_audio(
                    audio=buf,
                    filename=f"{word}.ogg",
                    caption=text,
                )
        else:
            message.reply_text(text=text)
