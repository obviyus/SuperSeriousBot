from telegram import Update, Bot
from howlongtobeatpy import HowLongToBeat


def hltb(bot: Bot, update: Update):
    message = update.message

    if len(message.text.strip().split(' ', 1)) >= 2:
        query = message.text.strip().split(' ', 1)[1]
    else:
        bot.send_message(
            chat_id=message.chat_id,
            text="*Usage:* `/hltb {GAME_NAME}`\n*Example:* `/hltb horizon zero dawn`",
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        return

    results = HowLongToBeat().search(query)

    if results is not None and len(results) > 0:
        # Return result with highest similarity to query
        best_guess = max(results, key=lambda element: element.similarity)
    else:
        bot.send_message(
            chat_id=message.chat_id,
            text="No entry found.",
            reply_to_message_id=message.message_id,
        )
        return

    # check if non-zero value exists for gameplay_main
    if best_guess.gameplay_main != -1:
        output = f'<b>{best_guess.gameplay_main_label}</b>: {best_guess.gameplay_main} {best_guess.gameplay_main_unit} '
    # check if non-zero value exists for gameplay_extra
    elif best_guess.gameplay_main_extra != -1:
        output = f'{best_guess.gameplay_main_extra_label}: {best_guess.gameplay_main_extra} {best_guess.gameplay_main_extra_unit} '
    else:
        bot.send_message(
            chat_id=message.chat_id,
            text="No entry found.",
            reply_to_message_id=message.message_id,
        )
        return

    output += f'<a href=\"{best_guess.game_image_url}\">&#8205;</a>'

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
        parse_mode='HTML',
        disable_web_page_preview=False,
    )
