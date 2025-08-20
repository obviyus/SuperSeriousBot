from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import deprecated, description, example, triggers, usage


@triggers(["tr"])
@example("/tr")
@usage("/tr")
@description("Transcribe an audio message. Reply to a message to transcribe it.")
@deprecated(
    "This command has been deprecated due to technical issues. "
    "Contact @obviyus if you have a use case for this command."
)
async def transcribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Transcribe an audio message.
    """
    if transcribe.deprecated:
        await update.message.reply_text(transcribe.deprecated)
        return
