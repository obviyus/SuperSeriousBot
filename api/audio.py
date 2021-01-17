from telegram import MessageEntity
from configuration import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram


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

    file_id_names: dict = {
        "/jogi": "jogi_file_id",
        "/pon": "punya_song_id",
        "/fw": "for_what_id",
    }

    if file_id_names[audio] not in data:
        data[file_id_names[audio]] = config[file_id_names[audio].upper()]

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
