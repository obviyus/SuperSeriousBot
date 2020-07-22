def kick(update, context):
    """Command to kick deep from group."""
    message = update.message
    chat_id = message.chat_id

    kicker = context.bot.get_chat_member(chat_id, message.from_user.id)

    # status can be ‘creator’, ‘administrator’, ‘member’, ‘restricted’, ‘left’
    # or ‘kicked’. Latter 3 can't send a message
    if kicker['status'] != "member":
        if message.reply_to_message:
            user_to_kick = message.reply_to_message.from_user
            try:
                context.bot.kick_chat_member(chat_id, user_to_kick.id)
                context.bot.unban_chat_member(chat_id, user_to_kick.id)
                text = f"Kicked {user_to_kick.first_name}."
            except Exception:
                text = "Couldn't kick, either I'm not an admin or the other user is."
        else:
            text = "Reply to the person who you want to kick."
    else:
        text = "Fuck off."

    message.reply_text(text=text)
