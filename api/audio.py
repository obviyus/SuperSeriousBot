from configuration import config


def jogi(update, context):
    """Post jogi"""
    message = update.message
    data = context.bot_data

    if "jogi_file_id" not in data:
        data["jogi_file_id"] = config["JOGI_FILE_ID"]

    # Failsafe since I'm not certain how long file_ids persist If they do forever we can keep this for pranks
    if message.from_user.username in config["AUDIO_RESTORE_USERS"] and update.effective_chat.type == "private" and message.reply_to_message:
        data["jogi_file_id"] = message.reply_to_message.voice.file_id
        message.reply_text(f"Jogi file ID set to: {data['jogi_file_id']}")
    else:
        message.reply_voice(voice=data["jogi_file_id"])


def forwhat(update, context):
    """Post for what"""
    message = update.message
    data = context.bot_data

    if "for_what_id" not in data:
        data["for_what_id"] = config["FOR_WHAT_ID"]

    # Failsafe since I'm not certain how long file_ids persist If they do forever we can keep this for pranks
    if message.from_user.username in config["AUDIO_RESTORE_USERS"] and update.effective_chat.type == "private" and message.reply_to_message:
        data["for_what_id"] = message.reply_to_message.voice.file_id
        message.reply_text(f"Jogi file ID set to: {data['for_what_id']}")
    else:
        message.reply_voice(voice=data["for_what_id"])


def pon(update, context):
    """Post punya's theme"""
    message = update.message
    data = context.bot_data

    if "punya_song_id" not in data:
        data["punya_song_id"] = config["PUNYA_SONG_ID"]

    # Failsafe since I'm not certain how long file_ids persist If they do forever we can keep this for pranks
    if message.from_user.username in config["AUDIO_RESTORE_USERS"] and update.effective_chat.type == "private" and message.reply_to_message:
        data["punya_song_id"] = message.reply_to_message.voice.file_id
        message.reply_text(f"Jogi file ID set to: {data['punya_song_id']}")
    else:
        message.reply_voice(voice=data["punya_song_id"])
