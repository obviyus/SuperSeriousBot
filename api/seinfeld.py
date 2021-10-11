from io import BytesIO
from pydub import AudioSegment

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def seinfeld(update: 'telegram.Update', _: 'telegram.ext.CallbackContext') -> None:
    """Add the seinfeld soundtrack to audio"""
    message: 'telegram.Message' = update.message
    audio: Union['telegram.Audio', 'telegram.Voice']

    if not message.reply_to_message:
        message.reply_text('Please reply to a voice note or music file')
        return
    elif message.reply_to_message.audio:
        audio = message.reply_to_message.audio
    elif message.reply_to_message.voice:
        audio = message.reply_to_message.voice
    else:
        message.reply_text('Please reply to a voice note or music file')
        return

    audio_file: BytesIO = BytesIO(audio.get_file().download_as_bytearray())

    seinfeld = AudioSegment.from_file('files/seinfeld_song.mp3').apply_gain(-10)
    overlayed = AudioSegment.from_file(audio_file).overlay(seinfeld, loop=True)

    output: BytesIO = BytesIO()
    overlayed.export(output, format='ogg', codec='libopus')

    message.reply_voice(output, filename='seinfeld.ogg')
