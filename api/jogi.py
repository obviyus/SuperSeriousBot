from configuration import config


def jogi(update, context):
    message = update.message
    data = context.bot_data

    if "jogi_file_id" not in data:
        data["jogi_file_id"] = config["JOGI_FILE_ID"]

    # Failsafe since I'm not certain how long file_ids persist If they do forever we can keep this for pranks
    if message.from_user.username in config["JOGI_FILE_RESTORE_USERS"] and update.effective_chat.type == "private" and message.reply_to_message:
        data["jogi_file_id"] = message.reply_to_message.voice.file_id
        message.reply_text(f"Jogi file ID set to: {data['jogi_file_id']}")
    else:
        message.reply_voice(voice=data["jogi_file_id"])
