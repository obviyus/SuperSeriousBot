from io import BytesIO
from typing import TYPE_CHECKING

from google.cloud import texttospeech

if TYPE_CHECKING:
    import telegram
    import telegram.ext

languages = {
    'ar': ['ar-XA', 'ar-XA-Wavenet-D'], 'bn': ['bn-IN', 'bn-IN-Wavenet-A'], 'en': ['en-GB', 'en-GB-Wavenet-F'],
    'es': ['es-US', 'es-US-Wavenet-A'], 'fi': ['fi-FI', 'fi-FI-Wavenet-A'], 'gu': ['gu-IN', 'gu-IN-Wavenet-A'],
    'ja': ['ja-JP', 'ja-JP-Wavenet-A'], 'kn': ['kn-IN', 'kn-IN-Wavenet-A'], 'ml': ['ml-IN', 'ml-IN-Wavenet-A'],
    'sv': ['sv-SE', 'sv-SE-Wavenet-A'], 'ta': ['ta-IN', 'ta-IN-Wavenet-A'], 'tr': ['tr-TR', 'tr-TR-Wavenet-A'],
    'ms': ['ms-MY', 'ms-MY-Wavenet-C'], 'pa': ['pa-IN', 'pa-IN-Wavenet-C'], 'cs': ['cs-CZ', 'cs-CZ-Wavenet-A'],
    'de': ['de-DE', 'de-DE-Wavenet-C'], 'fr': ['fr-FR', 'fr-FR-Wavenet-C'], 'hi': ['hi-IN', 'hi-IN-Wavenet-A'],
    'id': ['id-ID', 'id-ID-Wavenet-A'], 'it': ['it-IT', 'it-IT-Wavenet-B'], 'ko': ['ko-KR', 'ko-KR-Wavenet-B'],
    'ru': ['ru-RU', 'ru-RU-Wavenet-C'], 'uk': ['uk-UA', 'uk-UA-Wavenet-A'], 'cmn': ['cmn-TW', 'cmn-TW-Wavenet-A'],
    'da': ['da-DK', 'da-DK-Wavenet-A'], 'el': ['el-GR', 'el-GR-Wavenet-A'], 'fil': ['fil-PH', 'fil-PH-Wavenet-B'],
    'hu': ['hu-HU', 'hu-HU-Wavenet-A'], 'nb': ['nb-NO', 'nb-no-Wavenet-E'], 'nl': ['nl-NL', 'nl-NL-Wavenet-E'],
    'pt': ['pt-BR', 'pt-BR-Wavenet-A'], 'sk': ['sk-SK', 'sk-SK-Wavenet-A'], 'vi': ['vi-VN', 'vi-VN-Wavenet-C'],
    'pl': ['pl-PL', 'pl-PL-Wavenet-D'], 'ro': ['ro-RO', 'ro-RO-Wavenet-A']
}


def listvoices(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """List all voices supported by /tts"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str = "/tts Supported Wavenet Voices:\n"
    for code, attr in languages.items():
        text += f"\n`{code} - {attr[1]}`"

    message.reply_text(text)


def tts(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Convert text to speech in a given language using Google TTS"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str
    lang: str
    client = texttospeech.TextToSpeechClient.from_service_account_json('service_account.json')

    if not context.args:
        try:
            sentence: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
            synthesis_input = texttospeech.SynthesisInput(text=sentence)
            lang = 'ja'
        except AttributeError:
            message.reply_text(
                text="*Usage:* `/tts {LANG} - {SENTENCE}`\n"
                     "*Example:* `/tts ru - cyka blyat`\n"
                     "Defaults to `ja` if none provided.\n"
                     "Reply with `/tts` to a message to speak it in Japanese.",
            )
            return
    else:
        # [1:2] will return first item or empty list if the index doesn't exist
        if context.args[1:2] == ['-']:
            lang = context.args[0]
            if lang not in languages:
                message.reply_text("Invalid language code. Use /listvoices to see all supported languages.")
                return
            sentence = ' '.join(context.args[2:])
        else:
            lang = "ja"
            sentence = ' '.join(context.args)

        if not sentence.strip():
            message.reply_text(text="Nothing to speak.")
            return
        else:
            synthesis_input = texttospeech.SynthesisInput(text=sentence)

    voice = texttospeech.VoiceSelectionParams(
        language_code=languages[lang][0],
        name=languages[lang][1],
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    with BytesIO() as fp:
        fp.write(response.audio_content)
        fp.name = f'tts__{sentence[:10]}.ogg'
        fp.seek(0)
        message.reply_audio(audio=fp)
