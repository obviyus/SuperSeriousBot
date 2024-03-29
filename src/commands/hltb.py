from howlongtobeatpy import HowLongToBeat
from telegram import Update
from telegram.ext import ContextTypes

import commands
from utils.decorators import description, example, triggers, usage


@triggers(["hltb"])
@usage("/hltb [game]")
@example("/hltb Horizon Zero Dawn")
@description("Find how long a game takes to beat.")
async def hltb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find how long a game takes to beat"""
    if not context.args:
        await commands.usage_string(update.message, hltb)
        return

    game: str = " ".join(context.args) if context.args else ""
    text: str

    results = await HowLongToBeat().async_search(game, similarity_case_sensitive=False)

    if results:
        # Return result with the highest similarity to query
        best_guess = max(results, key=lambda element: element.similarity)

        # Check if non-zero value exists for main gameplay
        if best_guess.main_story != -1:
            text = (
                f"<b>{best_guess.game_name}</b>: "
                f"{best_guess.main_story} hours"
                f"<a href='{best_guess.game_image_url}'>&#8205;</a>"
            )
        # Check if non-zero value exists for main+extra gameplay
        elif best_guess.main_extra != -1:
            text = (
                f"<b>{best_guess.game_name}</b>: "
                f"{best_guess.main_story} hours"
                f"<a href='{best_guess.game_image_url}'>&#8205;</a>"
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
