from howlongtobeatpy import HowLongToBeat
from telegram import Update
from telegram.ext import ContextTypes

import utils


async def hltb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find how long a game takes to beat"""
    if not context.args:
        await utils.usage_string(update.message)
        return

    game: str = " ".join(context.args) if context.args else ""
    text: str

    results = HowLongToBeat().search(game, similarity_case_sensitive=False)

    if results:
        # Return result with the highest similarity to query
        best_guess = max(results, key=lambda element: element.similarity)

        # HLTB changed the image_url field to be a suffix to base URL
        image_url: str = "https://howlongtobeat.com" + best_guess.game_image_url

        # Check if non-zero value exists for main gameplay
        if best_guess.gameplay_main != -1:
            text = (
                f"<b>{best_guess.gameplay_main_label}</b>: "
                f"{best_guess.gameplay_main} {best_guess.gameplay_main_unit}"
                f"<a href='{image_url}'>&#8205;</a>"
            )
        # Check if non-zero value exists for main+extra gameplay
        elif best_guess.gameplay_main_extra != -1:
            text = (
                f"<b>{best_guess.gameplay_main_extra_label}</b>: "
                f"{best_guess.gameplay_main_extra} {best_guess.gameplay_main_extra_unit}"
                f"<a href='{image_url}'>&#8205;</a>"
            )
        else:
            text = "No hours recorded."
    else:
        text = "No entry found."

    await update.message.reply_text(
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )
