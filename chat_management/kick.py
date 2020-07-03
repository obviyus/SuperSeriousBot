def kick(bot, update):
    msg = update.message
    chat_id = msg.chat_id

    kicker = bot.get_chat_member(chat_id, msg.from_user.id)

    if kicker['status'] != "member":
        if update.message.reply_to_message:
            user_to_kick = update.message.reply_to_message.from_user
        else:
            bot.send_message(chat_id=chat_id,
                             text="Reply to the person who you want to kick.",
                             reply_to_message_id=msg.message_id)
            return
    else:
        bot.send_message(chat_id=chat_id,
                         text=f"Fuck off.",
                         reply_to_message_id=msg.message_id)
        return

    try:
        bot.kick_chat_member(chat_id, user_to_kick.id)
        bot.unban_chat_member(chat_id, user_to_kick.id)
        bot.send_message(chat_id=chat_id,
                         text=f"Kicked {user_to_kick.first_name}.",
                         reply_to_message_id=msg.message_id)
    except:
        bot.send_message(chat_id=chat_id,
                         text="Couldn't kick, either I'm not an admin or the other user is.",
                         reply_to_message_id=msg.message_id)
