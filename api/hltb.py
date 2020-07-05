from telegram import Update, Bot
from howlongtobeatpy import HowLongToBeat

def hltb(bot: Bot, update: Update):
    message = update.message
    try:
        query = message.text.strip().split(' ', 1)[1]
    except IndexError:
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
    
    output = f'*{best_guess.gameplay_main_label}*: {best_guess.gameplay_main} {best_guess.gameplay_main_unit}'

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
        parse_mode='Markdown',
    )
