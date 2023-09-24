from imdb import Cinemagoer
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils.cleaner

ia = Cinemagoer()


async def button_builder(movie) -> InlineKeyboardMarkup:
    """
    Builds the button for the movie
    """
    if movie["kind"] == "movie":
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Launch Stream 🍿",
                        url=f"https://vidsrc.to/embed/movie/tt{movie['id']}",
                    )
                ]
            ]
        )


async def inline_show_search(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Searches for a TV show or movie
    """
    query = update.inline_query.query
    if len(query) < 3:
        return

    search_results = ia.search_movie_advanced(query, results=10)
    results, seen = [], set()

    for movie in search_results:
        movie = utils.get_fields(movie)
        if movie["id"] not in seen:
            seen.add(movie["id"])
        else:
            continue

        results.append(
            InlineQueryResultArticle(
                id=movie["id"],
                title=f"{movie['title']} ({movie['year']})",
                description=movie["plot"],
                thumbnail_url=movie["cover url"],
                input_message_content=InputTextMessageContent(
                    f"<b>Title</b>: {movie['title']} <b>({movie['year']})</b>"
                    f"\n<b>Rating</b>: ⭐ {movie['rating']} / 10"
                    f"\n<b>Runtime</b>: {movie['runtime']} minutes"
                    f"\n<b>Genre</b>: {movie['genres']}"
                    f"\n<b>Directors</b>: {movie['directors']}"
                    f"\n<b>Cast</b>: {movie['cast']}"
                    f"\n\n{movie['plot']}"
                    f"<a href='{movie['full-size cover url']}'>&#8205;</a>",
                    parse_mode=ParseMode.HTML,
                ),
                reply_markup=await button_builder(movie),
            )
        )

    if len(results) == 0:
        results.append(
            InlineQueryResultArticle(
                id="0",
                title="No results found.",
                input_message_content=InputTextMessageContent(
                    "No results found. Try searching with a different title."
                ),
            )
        )

    await update.inline_query.answer(results)
