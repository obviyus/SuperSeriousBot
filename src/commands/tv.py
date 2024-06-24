import asyncio

import aiohttp
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

import utils

ia = Cinemagoer()


async def link_builder(movie):
    if "kind" not in movie.data:
        return None

    content_url = None
    if movie.data["kind"] == "movie":
        content_url = f"https://vidsrc.to/embed/movie/tt{movie.movieID}"
    elif movie.data["kind"] == "tv series":
        content_url = f"https://vidsrc.to/embed/tv/tt{movie.movieID}"

    if not content_url:
        return

    async with aiohttp.ClientSession() as session:
        async with session.head(content_url) as response:
            if response.status != 200:
                return

    content_url_cache[movie.movieID] = content_url
    return content_url


content_url_cache = {}


async def inline_show_search(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Searches for a TV show or movie
    """
    query = update.inline_query.query
    if len(query) < 3:
        return

    search_results = ia.search_movie(query, results=5)
    results, seen = [], set()

    # Filter out objects that don't have a valid content link
    tasks = [link_builder(movie) for movie in search_results]
    content_urls = await asyncio.gather(*tasks)

    for movie, content_url in zip(search_results, content_urls):
        if not content_url:
            continue

        if movie.movieID not in seen:
            seen.add(movie.movieID)
        else:
            continue

        results.append(
            InlineQueryResultArticle(
                id=movie.movieID,
                title=f"{movie['title']} {movie['year'] if 'year' in movie else ''}",
                thumbnail_url=movie["cover url"] if "cover url" in movie else None,
                input_message_content=InputTextMessageContent("Loading..."),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Launch Stream 🍿",
                                url=content_url,
                            )
                        ]
                    ]
                ),
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


async def handle_chosen_movie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handles inline query results.
    """
    if update.chosen_inline_result.result_id == "0":
        return

    movie = ia.get_movie(update.chosen_inline_result.result_id)
    movie = utils.get_fields(movie)

    await context.bot.edit_message_text(
        f"<b>Title</b>: {movie['title']} <b>({movie['year']})</b>"
        f"\n<b>Rating</b>: ⭐ {movie['rating']} / 10"
        f"\n<b>Runtime</b>: {movie['runtime']} minutes"
        f"\n<b>Genre</b>: {movie['genres']}"
        f"\n<b>Directors</b>: {movie['directors']}"
        f"\n<b>Cast</b>: {movie['cast']}"
        f"\n\n{movie['plot'][0:500]}..."
        f"<a href='{movie['full-size cover url']}'>&#8205;</a>",
        parse_mode=ParseMode.HTML,
        inline_message_id=update.chosen_inline_result.inline_message_id,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Launch Stream 🍿",
                        url=content_url_cache[update.chosen_inline_result.result_id],
                    )
                ]
            ]
        ),
    )
