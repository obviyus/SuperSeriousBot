import time
from collections import defaultdict

import dateparser
import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ContextTypes

import utils.cleaner
from config.db import sqlite_conn
from config.logger import logger
from utils.decorators import description, example, triggers, usage

TVMAZE_SEARCH_ENDPOINT = "https://api.tvmaze.com/search/shows"


async def keyboard_builder(user_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """
    Builds a keyboard of the user's subscribed TV shows.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "⏱ Show ETA", callback_data=f"show_eta:{user_id},{chat_id}"
            )
        ]
    ]

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """SELECT tv_shows.show_id, tv_shows.show_name
            FROM tv_notifications
                     JOIN tv_shows ON tv_notifications.show_id = tv_shows.show_id
                     JOIN main.tv_opt_in ON tv_notifications.user_id = tv_opt_in.user_id
            WHERE tv_notifications.user_id = ? AND tv_opt_in.chat_id = ?
            ORDER BY tv_shows.show_name""",
        (user_id, chat_id),
    )

    for show in cursor.fetchall():
        keyboard.append(
            [
                InlineKeyboardButton(
                    show["show_name"],
                    callback_data=f"""rts:{show["show_id"]},{user_id}""",
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


async def eta_keyboard_builder(update: Update, context: CallbackContext) -> None:
    """
    Builds a keyboard of the ETA to next episode of user's subscribed TV shows.
    """
    query = update.callback_query
    user_id, chat_id = query.data.replace("show_eta:", "").split(",")

    keyboard = [
        [
            InlineKeyboardButton(
                "⏱ Hide ETA", callback_data=f"hide_eta:{user_id},{chat_id}"
            )
        ]
    ]

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """SELECT tv_shows.show_id, tv_shows.show_name, tv_shows.next_episode_time
            FROM tv_notifications
                     JOIN tv_shows ON tv_notifications.show_id = tv_shows.show_id
                     JOIN main.tv_opt_in ON tv_notifications.user_id = tv_opt_in.user_id
            WHERE tv_notifications.user_id = ? AND tv_opt_in.chat_id = ?
            ORDER BY tv_shows.show_name""",
        (user_id, chat_id),
    )

    for show in cursor.fetchall():
        print(show["show_name"], show["next_episode_time"])
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"""{await utils.readable_time(show["next_episode_time"]) if show["next_episode_time"] else "No next episode."}""",
                    callback_data="none",
                )
            ]
        )

    await context.bot.edit_message_text(
        text=f"ETA of your shows in this chat:",
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def tv_show_button(update: Update, context: CallbackContext) -> None:
    """Remove a TV show from the watchlist."""
    query = update.callback_query
    show_id, user_id = query.data.replace("rts:", "").split(",")

    # Check user that pressed the button is the same as the user that added the show
    if query.from_user.id != int(user_id):
        await query.answer("You can't remove shows from other users' watchlist.")
        return

    cursor = sqlite_conn.cursor()

    # Remove show from watchlist
    cursor.execute(
        "DELETE FROM tv_notifications WHERE show_id = ? AND user_id = ?",
        (show_id, user_id),
    )

    await query.answer(f"Removed from your watchlist.")
    await context.bot.edit_message_text(
        text=f"List of your shows in this chat. Tap on a show to remove it from your watchlist:",
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        reply_markup=await keyboard_builder(user_id, update.message.chat_id),
    )


@triggers(["tv"])
@description(
    "Subscribe to TV show notifications. Use /tv to list your subscriptions. Add new shows by searching for them in the inline query."
)
@usage("/tv")
@example("/tv")
async def opt_in_tv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays a user's watchlist.
    """
    cursor = sqlite_conn.cursor()

    # Check if user has opted in
    cursor.execute(
        "SELECT * FROM tv_opt_in WHERE user_id = ? AND chat_id = ?",
        (update.effective_user.id, update.effective_chat.id),
    )

    if cursor.fetchone():
        # Show all shows for the user in this chat
        await update.message.reply_text(
            "List of your shows in this chat. Tap on a show to remove it from your watchlist:",
            reply_markup=await keyboard_builder(
                update.effective_user.id, update.message.chat_id
            ),
        )
        return

    # Add user to list
    cursor.execute(
        "INSERT INTO tv_opt_in (user_id, chat_id, username) VALUES (?, ?, ?)",
        (
            update.effective_user.id,
            update.message.chat.id,
            update.message.from_user.username,
        ),
    )

    await update.message.reply_text(
        f"You have opted in for TV Episode notifications in {update.message.chat.title}."
    )


async def inline_show_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Searches for a TV show.
    """
    query = update.inline_query.query
    if len(query) < 3:
        return

    # Query TVMaze API for the name of the show
    async with httpx.AsyncClient() as client:
        response = await client.get(
            TVMAZE_SEARCH_ENDPOINT,
            params={"q": query},
        )

    results = []

    for show in response.json():
        show = show["show"]
        results.append(
            InlineQueryResultArticle(
                id=show["id"],
                title=show["name"],
                description=utils.cleaner.scrub_html_tags(show["summary"]),
                thumb_url=show["image"]["medium"] if show["image"] else "",
                input_message_content=InputTextMessageContent(
                    f"""Added <b>{show['name']}</b> to your watchlist.""",
                    parse_mode=ParseMode.HTML,
                ),
            )
        )

    await update.inline_query.answer(results)


async def insert_new_show(show_id: int) -> None:
    """
    Given an ID, insert a new show in the DB.
    """

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.tvmaze.com/shows/{show_id}?embed=nextepisode"
        )
        response = response.json()

    if "_embedded" in response and "nextepisode" in response["_embedded"]:
        airing_time = response["_embedded"]["nextepisode"]["airstamp"]
        airing_date = dateparser.parse(airing_time).timestamp()

        episode_string = f"""<b>{response["name"]}</b> - {response['_embedded']['nextepisode']['name']} (Season {response['_embedded']['nextepisode']['season']}: Episode {response['_embedded']['nextepisode']['number']})"""

        cursor = sqlite_conn.cursor()
        cursor.execute(
            "UPDATE tv_shows SET next_episode_time = ?, next_episode_name = ?, sent = 0 WHERE show_id = ?",
            (airing_date, episode_string, show_id),
        )


async def inline_result_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handles the inline query result.
    """
    show_id = int(update.chosen_inline_result.result_id)

    # Check if the show_id exists in the DB
    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT * FROM tv_shows WHERE show_id = ?",
        (show_id,),
    )

    if not cursor.fetchone():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.tvmaze.com/shows/{show_id}?embed=nextepisode"
            )
            response = response.json()

        cursor.execute(
            "INSERT INTO tv_shows (show_id, show_name, show_image) VALUES (?, ?, ?)",
            (
                show_id,
                response["name"],
                response["image"]["original"],
            ),
        )

        await insert_new_show(show_id)

        # Add show to user's watchlist
    cursor.execute(
        "INSERT INTO tv_notifications (user_id, show_id) VALUES (?, ?)",
        (
            update.chosen_inline_result.from_user.id,
            update.chosen_inline_result.result_id,
        ),
    )


async def worker_next_episode(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker that checks for upcoming episodes of shows in DB.
    """
    current_time = time.time()

    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT * FROM tv_shows WHERE next_episode_time <= ? OR next_episode_time IS NULL",
        (current_time,),
    )

    for show in cursor.fetchall():
        time.sleep(1)
        logger.info(f"Checking for new episodes of: {show['show_name']}")
        await insert_new_show(show["show_id"])

    # Some shows update their episode titles
    cursor.execute(
        "SELECT * FROM tv_shows",
        (current_time,),
    )

    for show in cursor.fetchall():
        time.sleep(1)
        logger.info(f"Checking for new titles of: {show['show_name']}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"""https://api.tvmaze.com/shows/{show["show_id"]}?embed=nextepisode"""
            )
            response = response.json()

        if "_embedded" in response and "nextepisode" in response["_embedded"]:
            episode_string = f"""<b>{response["name"]}</b> - {response['_embedded']['nextepisode']['name']} (Season {response['_embedded']['nextepisode']['season']}: Episode {response['_embedded']['nextepisode']['number']})"""
            if episode_string != show["next_episode_name"]:
                cursor.execute(
                    "UPDATE tv_shows SET next_episode_name = ? WHERE show_id = ?",
                    (episode_string, show["show_id"]),
                )


async def worker_episode_notifier(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker that checks if an upcoming episode has aired and notifies the user.
    """

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """SELECT * 
        FROM tv_shows
        WHERE next_episode_time <= ? AND sent = 0
        """,
        (time.time(),),
    )

    for show in cursor.fetchall():
        logger.info(f"Sending notification for {show['show_name']}.")
        message_queue = defaultdict(list)

        # Get all users that are subscribed to the show
        cursor.execute(
            "SELECT * FROM tv_notifications WHERE show_id = ?", (show["show_id"],)
        )
        for user in cursor.fetchall():
            # Get all groups that the user is subscribed in
            cursor.execute(
                "SELECT * FROM tv_opt_in WHERE user_id = ?", (user["user_id"],)
            )
            for group in cursor.fetchall():
                message_queue[group["chat_id"]].append("@" + group["username"])

        # Send message to each group
        for chat_id in message_queue:
            try:
                await context.bot.send_message(
                    chat_id,
                    f"{show['next_episode_name']} has aired! \n\n{' '.join(message_queue[chat_id])}"
                    f"<a href='{show['show_image']}'>&#8205;</a>",
                    parse_mode=ParseMode.HTML,
                )
            except BadRequest:
                logger.error(
                    f"Failed to send message to {chat_id}. Removing all subscriptions."
                )
                cursor.execute("DELETE FROM tv_opt_in WHERE chat_id = ?", (chat_id,))
            time.sleep(1)

        cursor.execute(
            "UPDATE tv_shows SET sent = 1 WHERE show_id = ?", (show["show_id"],)
        )
