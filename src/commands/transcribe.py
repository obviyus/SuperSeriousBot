import whisper
from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import description, example, triggers, usage

model = whisper.load_model("base")


@triggers(["tr"])
@example("/tr")
@usage("/tr")
@description("Transcribe an audio message. " "Reply to a message to transcribe it.")
async def transcribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Transcribe an audio message.
    """
    if update.message.reply_to_message:
        try:
            voice = (
                update.message.reply_to_message.voice
                or update.message.reply_to_message.audio
            )

            await (await context.bot.getFile(voice.file_id)).download(
                custom_path="audio.ogg"
            )

            result = model.transcribe("audio.ogg")
            await update.message.reply_text(result["text"])
        except AttributeError:
            await update.message.reply_text("No audio found.")
    else:
        await update.message.reply_text("Reply to an audio message to transcribe it.")
