def ban(bot, update):
    msg = update.message
    chat_id = msg.chat_id

    banner = bot.get_chat_member(chat_id, msg.from_user.id)

    if banner.user.username == 'e_to_the_i_pie' or banner['status'] != 'member':
        if update.message.reply_to_message:
            user_to_ban = update.message.reply_to_message.from_user
            try:
                bot.kick_chat_member(chat_id, user_to_ban.id)
                bot.send_message(
                    chat_id=chat_id,
                    text=f"Banned {user_to_ban.first_name}.",
                    reply_to_message_id=msg.message_id
                )
            except Exception:
                bot.send_message(
                    chat_id=chat_id,
                    text="Couldn't ban, either I'm not an admin or the other user is.",
                    reply_to_message_id=msg.message_id
                )
        else:
            bot.send_message(
                chat_id=chat_id,
                text="Reply to the person who you want to ban.",
                reply_to_message_id=msg.message_id
            )
    else:
        bot.send_message(
            chat_id=chat_id,
            text="Fuck off.",
            reply_to_message_id=msg.message_id
        )
