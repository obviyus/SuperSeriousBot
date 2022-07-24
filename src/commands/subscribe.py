import html
from asyncio import sleep

import dateparser
from asyncpraw import models
from asyncprawcore import BadRequest, Forbidden, NotFound, Redirect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import utils
from config.db import sqlite_conn
from .reddit_comment import reddit


async def make_response(post: models.Submission, username: str) -> str:
    return f"{post.url}\n\n<a href='https://reddit.com{post.permalink}'>/r/{post.subreddit.display_name};</a> @{username}"


async def subscribe_reddit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Subscribe to a subreddit for daily posts.
    """
    if not context.args:
        await utils.usage_string(update.message)
        return

    subreddit = context.args[0].replace("r/", "").lower()
    if not subreddit:
        await utils.usage_string(update.message)
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM reddit_subscriptions WHERE subreddit_name = ? COLLATE NOCASE AND group_id = ?;
        """,
        (subreddit, update.message.chat_id),
    )

    result = cursor.fetchone()
    if result:
        await update.message.reply_text(
            f"Already subscribed to /r/{html.escape(subreddit)} in this group by "
            f"@{html.escape(context.bot.get_chat_member(result['group_id'], result['receiver_id']))}.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        posts = (await reddit.subreddit(subreddit)).hot(limit=1)
        async for post in posts:
            subreddit = post.subreddit.display_name

        cursor.execute(
            """
            INSERT INTO `reddit_subscriptions` (`group_id`, `subreddit_name`, `receiver_username`, `receiver_id`) VALUES (?, ?, ?, ?);
            """,
            (
                update.message.chat.id,
                subreddit,
                update.message.from_user.username,
                update.message.from_user.id,
            ),
        )

        await update.message.reply_text(
            f"Subscribed to <b>/r/{html.escape(subreddit)}</b>.",
            parse_mode=ParseMode.HTML,
        )
    except (NotFound, BadRequest, Redirect):
        await update.message.reply_text(text="Subreddit not found or banned")
    except Forbidden:
        await update.message.reply_text(text="Subreddit is quarantined or private")


async def keyboard_builder(user_id: int, group_id: int) -> InlineKeyboardMarkup:
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM reddit_subscriptions WHERE group_id = ? AND receiver_id = ?;
        """,
        (user_id, group_id),
    )

    keyboard = []

    for subreddit in cursor.fetchall():
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"""{subreddit["subreddit_name"]} ({await utils.readable_time(int(dateparser.parse(subreddit["create_time"]).timestamp()))})""",
                    callback_data=f"""unsubscribe_reddit:{subreddit["subreddit_name"]},{subreddit["receiver_id"]}""",
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


async def list_reddit_subscriptions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    List all Reddit subscriptions for a user.
    """

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM reddit_subscriptions WHERE group_id = ? AND receiver_id = ?;
        """,
        (update.message.chat_id, update.message.from_user.id),
    )

    if not cursor.fetchone():
        await update.message.reply_text(
            text="You are not subscribed to any subreddits."
        )
        return

    await update.message.reply_text(
        text="You are subscribed to the following subreddits in this group. Tap to remove:",
        reply_markup=await keyboard_builder(
            update.message.from_user.id, update.message.chat_id
        ),
    )


async def reddit_subscription_button_handler(
    update: Update, context: CallbackContext
) -> None:
    """Remove a Reddit subscription."""
    query = update.callback_query
    subreddit_name, user_id = query.data.replace("unsubscribe_reddit:", "").split(",")

    # Check user that pressed the button is the same as the user that added the show
    if query.from_user.id != int(user_id):
        await query.answer(
            "You can't remove subreddits from other users' subscriptions."
        )
        return

    cursor = sqlite_conn.cursor()

    # Remove show from watchlist
    cursor.execute(
        "DELETE FROM reddit_subscriptions WHERE subreddit_name = ? AND receiver_id = ?",
        (subreddit_name, user_id),
    )

    await query.answer(f"Removed /r/{subreddit_name} from your watchlist.")
    await context.bot.edit_message_text(
        text="You are subscribed to the following subreddits in this group. Tap to remove:",
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        reply_markup=await keyboard_builder(user_id, query.message.chat.id),
    )


async def worker_reddit_subscriptions(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker function to scan dB and send posts.
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT * FROM reddit_subscriptions;
        """
    )

    async def poster(group_id: int, user_id: int, subreddit_name: str) -> None:
        for post in (await reddit.subreddit(subreddit_name)).hot(limit=3):
            if post.stickied:
                continue

            try:
                await context.bot.send_message(
                    group_id,
                    await make_response(
                        post,
                        context.bot.get_chat_member(group_id, user_id).user.username,
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except (NotFound, BadRequest, Redirect, Forbidden):
                cursor.execute(
                    """
                    DELETE FROM reddit_subscriptions WHERE subreddit_name = ? AND receiver_id = ?;
                    """
                )

                await context.bot.send_message(
                    group_id,
                    f"Removed /r/{subreddit_name} from your watchlist because it was deleted or banned.",
                    parse_mode=ParseMode.HTML,
                )

    for row in cursor.fetchall():
        await poster(row["group_id"], row["receiver_id"], row["subreddit_name"])
        await sleep(1)
