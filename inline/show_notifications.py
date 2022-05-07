import logging
import time

import dateparser
import re
import sqlite3
import requests
from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ParseMode,
)
from telegram.ext import CallbackContext

TVMAZE_SEARCH_ENDPOINT = "http://api.tvmaze.com/search/shows"

conn = sqlite3.connect("/db/groups.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `tv_opt_in` (
        `id` INTEGER PRIMARY KEY,
        `user_id` INTEGER NOT NULL,
        `chat_id` VARCHAR(255) NOT NULL,
        `username` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `tv_notifications` (
        `id` INTEGER PRIMARY KEY,
        `user_id` VARCHAR(255) NOT NULL,
        `show_id` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `tv_shows` (
        `id` INTEGER PRIMARY KEY,
        `show_id` VARCHAR(255) NOT NULL,
        `show_name` VARCHAR(255) NOT NULL,
        `show_image` VARCHAR(255) NOT NULL,
        `next_episode_time` INTEGER NULL,
        `next_episode_name` VARCHAR(255) NULL,
        `sent` INTEGER NOT NULL DEFAULT 0,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)


def opt_in_tv(update: Update, context: CallbackContext) -> None:
    """Opt-in for TV Episode notifications feature."""
    text: str

    # Check if user has opted in
    cursor.execute(
        "SELECT * FROM tv_opt_in WHERE user_id = ? AND chat_id = ?",
        (update.effective_user.id, update.effective_chat.id),
    )
    if cursor.fetchone():
        cursor.execute(
            "DELETE FROM tv_opt_in WHERE user_id = ? AND chat_id = ?",
            (update.effective_user.id, update.effective_chat.id),
        )
        update.message.reply_text(
            f"You have opted-out of TV Episode notifications in {update.message.chat.title}."
        )
        return

    # Add user to list
    cursor.execute(
        "INSERT INTO tv_opt_in (user_id, chat_id, username) VALUES (?, ?, ?)",
        (
            update.effective_user.id,
            update.message.chat.id,
            update.effective_user.username,
        ),
    )

    update.message.reply_text(
        f"You have opted in for TV Episode notifications in {update.message.chat.title}."
    )

    conn.commit()


def inline_show_query(update: Update, context: CallbackContext) -> None:
    """Handle the inline query."""
    query = update.inline_query.query

    if len(query) < 3:
        return

    # Query TVMaze API for the name of the show
    response = requests.get(TVMAZE_SEARCH_ENDPOINT, params={"q": query})
    results = []

    for show in response.json():
        show = show["show"]
        results.append(
            InlineQueryResultArticle(
                id=show["id"],
                title=show["name"],
                description=re.sub("<[^<]+?>", "", show["summary"]),
                thumb_url=show["image"]["medium"],
                input_message_content=InputTextMessageContent(
                    f"""Added <b>{show['name']}</b> to your watchlist.""",
                    parse_mode="HTML",
                ),
            )
        )

    update.inline_query.answer(results)


def load_new_episode(show_id: int) -> None:
    response = requests.get(
        f"https://api.tvmaze.com/shows/{show_id}?embed=nextepisode"
    ).json()

    if response["_embedded"] and response["_embedded"]["nextepisode"]:
        # Get next episode time
        airstamp = response["_embedded"]["nextepisode"]["airstamp"]
        airdate = dateparser.parse(airstamp).timestamp()

        episode_name = f"""<b>{response["name"]}</b> - {response['_embedded']['nextepisode']['name']} (Season {response['_embedded']['nextepisode']['season']}: Episode {response['_embedded']['nextepisode']['number']})"""

        cursor.execute(
            "UPDATE tv_shows SET next_episode_time = ?, next_episode_name = ?, sent = 0 WHERE show_id = ?",
            (airdate, episode_name, show_id),
        )

        conn.commit()

        logging.info(f"""Loaded new episode for show {response["name"]}.""")


def show_result_handler(update: Update, context: CallbackContext) -> None:
    """Handle a user's selection."""
    if update.chosen_inline_result.result_id == "tv_opt_in":
        return

    logging.info(f"{update.chosen_inline_result.result_id} was chosen.")

    # Check if show exists in database
    cursor.execute(
        "SELECT * FROM tv_shows WHERE show_id = ?",
        (update.chosen_inline_result.result_id,),
    )
    if not cursor.fetchone():
        response = requests.get(
            f"https://api.tvmaze.com/shows/{update.chosen_inline_result.result_id}?embed=nextepisode"
        ).json()

        cursor.execute(
            "INSERT INTO tv_shows (show_id, show_name, show_image) VALUES (?, ?, ?)",
            (
                update.chosen_inline_result.result_id,
                response["name"],
                response["image"]["original"],
            ),
        )

        load_new_episode(int(update.chosen_inline_result.result_id))

    # Add show to user's watchlist
    cursor.execute(
        "INSERT INTO tv_notifications (user_id, show_id) VALUES (?, ?)",
        (
            update.chosen_inline_result.from_user.id,
            update.chosen_inline_result.result_id,
        ),
    )

    conn.commit()


def next_episode_worker(context: CallbackContext) -> None:
    """Worker that checks for upcoming episodes."""
    current_unix_time = time.time()

    cursor.execute(
        "SELECT * FROM tv_shows WHERE next_episode_time <= ? OR next_episode_time IS NULL",
        (current_unix_time,),
    )
    for show in cursor.fetchall():
        logging.info(f"Checking {show['show_name']} for new episodes.")
        load_new_episode(show["show_id"])


def episode_notifier_worker(context: CallbackContext) -> None:
    """Worker that checks if an upcoming episode has aired."""
    current_unix_time = time.time()

    cursor.execute(
        "SELECT * FROM tv_shows WHERE next_episode_time <= ? AND sent = 0",
        (current_unix_time,),
    )
    for show in cursor.fetchall():
        logging.info(f"Sending notification for {show['show_name']}.")
        message_queue = {}

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
                if group["chat_id"] not in message_queue:
                    message_queue[group["chat_id"]] = ["@" + group["username"]]
                else:
                    message_queue[group["chat_id"]].append("@" + group["username"])

        # Send message to each group
        for chat_id in message_queue:
            context.bot.send_message(
                chat_id,
                f"{show['next_episode_name']} has aired! \n\n{' '.join(message_queue[chat_id])}"
                f"<a href='{show['show_image']}'>&#8205;</a>",
                parse_mode=ParseMode.HTML,
            )

        cursor.execute(
            "UPDATE tv_shows SET sent = 1 WHERE show_id = ?", (show["show_id"],)
        )
        conn.commit()
