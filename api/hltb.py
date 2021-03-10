from typing import TYPE_CHECKING, Optional, List

from howlongtobeatpy import HowLongToBeat

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def hltb(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Find how long a game takes to beat"""

    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    game: str = ' '.join(context.args) if context.args else ''
    text: str

    if not game:
        text = "*Usage:* `/hltb {GAME_NAME}`\n" \
               "*Example:* `/hltb horizon zero dawn`"
    else:
        results: Optional[List] = HowLongToBeat().search(game, similarity_case_sensitive=False)

        if results:
            # Return result with highest similarity to query
            best_guess = max(results, key=lambda element: element.similarity)

            # check if non-zero value exists for main gameplay
            if best_guess.gameplay_main != -1:
                text = f"<b>{best_guess.gameplay_main_label}</b>: " \
                       f"{best_guess.gameplay_main} {best_guess.gameplay_main_unit}" \
                       f"<a href='{best_guess.game_image_url}'>&#8205;</a>"
            # check if non-zero value exists for main+extra gameplay
            elif best_guess.gameplay_main_extra != -1:
                text = f"<b>{best_guess.gameplay_main_extra_label}</b>: " \
                       f"{best_guess.gameplay_main_extra} {best_guess.gameplay_main_extra_unit}" \
                       f"<a href='{best_guess.game_image_url}'>&#8205;</a>"
            else:
                text = "No hours recorded."
        else:
            text = "No entry found."

    message.reply_text(
        text=text,
        parse_mode='HTML',
        disable_web_page_preview=False,
    )
