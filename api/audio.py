from typing import TYPE_CHECKING
from configuration import config
from telegram import MessageEntity

if TYPE_CHECKING:
    import telegram
    import telegram.ext

# Only relevant to primary SSG Bot
file_id = {
    "FOR_WHAT_ID": "AwACAgUAAxkBAAIOal-S4UbuMjFYVNMuKnHyRXrEQQkMAAJ8AgACrPiZVLggqYXKbCQwGwQ",
    "JOGI_FILE_ID": "AwACAgUAAxkBAAIBMV8z20JkqdmtvoHeXN-GpEU0U6tnAAJQAQACi8dhVDDR-g1eKeOWGgQ",
    "PUNYA_SONG_ID": "AwACAgUAAxkBAAIOU1-S4GftDoRxFQG3w7-BOutFA4PMAAJ5AgACrPiZVEFEWFLP89YXGwQ",
}


def audio(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Post audio"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    data: dict = context.bot_data
    audio: str
    if update.message.caption:
        audio = list(message.parse_caption_entities([MessageEntity.BOT_COMMAND]).values())[0]
    elif update.message.text:
        audio = list(message.parse_entities([MessageEntity.BOT_COMMAND]).values())[0]
    else:
        return

    audio = audio.partition('@')[0]

    file_id_names: dict = {
        "/jogi": "JOGI_FILE_ID",
        "/pon": "PUNYA_SONG_ID",
        "/fw": "FOR_WHAT_ID",
    }

    if file_id_names[audio] not in data:
        data[file_id_names[audio]] = file_id[file_id_names[audio]]

    # Failsafe since I'm not certain how long file_ids persist If they do forever we can keep this for pranks
    if (
            message.from_user
            and message.from_user.username in config["AUDIO_RESTORE_USERS"]
            and update.effective_chat
            and update.effective_chat.type == "private"
            and message.reply_to_message
            and message.reply_to_message.voice
    ):
        data[file_id_names[audio]] = message.reply_to_message.voice.file_id
        message.reply_text(f"Jogi file ID set to: {data[file_id_names[audio]]}")
    else:
        if message.reply_to_message:
            message.reply_to_message.reply_voice(voice=data[file_id_names[audio]])
        else:
            message.reply_voice(voice=data[file_id_names[audio]])
