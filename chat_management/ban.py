from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def ban(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Ban deep from group"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return
    chat_id: int = message.chat_id
    text: str

    banner: telegram.ChatMember = context.bot.get_chat_member(
        chat_id, message.from_user.id
    )

    # status can be ‘creator’, ‘administrator’, ‘member’, ‘restricted’, ‘left’
    # or ‘kicked’. Latter 3 can't send a message
    if banner["status"] != "member":
        if message.reply_to_message:
            user_to_ban: telegram.User = message.reply_to_message.from_user
            try:
                context.bot.kick_chat_member(chat_id, user_to_ban.id)
                text = f"Banned {user_to_ban.first_name}."
            except telegram.error.TelegramError:
                text = "Couldn't ban, either I'm not an admin or the other user is."
        else:
            text = "Reply to the person who you want to ban."
    else:
        text = "Fuck off."

    message.reply_text(text=text)
