import asyncio
import html

import dateparser
from asyncprawcore import BadRequest, Forbidden, NotFound, Redirect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes

import commands
import utils
from config import logger
from config.db import get_db
from utils.decorators import api_key, description, example, triggers, usage
from .randdit import make_response
from .reddit_comment import reddit


@triggers(["sub"])
@api_key("REDDIT")
@example("/sub Formula1")
@usage("/sub [subreddit]")
@description("Subscribe to a subreddit for daily post notifications.")
async def subscribe_reddit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Subscribe to a subreddit for daily posts.
    """
    if not context.args:
        await commands.usage_string(update.message, subscribe_reddit)
        return

    subreddit = context.args[0].replace("r/", "").lower()
    if not subreddit:
        await commands.usage_string(update.message, subscribe_reddit)
        return

    async with get_db(write=True) as conn:
        async with conn.execute(
            """
            SELECT * FROM reddit_subscriptions WHERE subreddit_name = ? COLLATE NOCASE AND group_id = ?;
            """,
            (subreddit, update.message.chat_id),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            await update.message.reply_text(
                f"Already subscribed to /r/{html.escape(subreddit)} in this group by "
                f"@{html.escape(await context.bot.get_chat_member(result['group_id'], result['receiver_id']))}.",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            posts = (await reddit.subreddit(subreddit)).hot(limit=1)
            async for post in posts:
                subreddit = post.subreddit.display_name

            await conn.execute(
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
            await conn.commit()

            await update.message.reply_text(
                f"Subscribed to <b>/r/{html.escape(subreddit)}</b>.",
                parse_mode=ParseMode.HTML,
            )
        except (NotFound, BadRequest, Redirect):
            await update.message.reply_text(text="Subreddit not found or banned")
        except Forbidden:
            await update.message.reply_text(text="Subreddit is quarantined or private")


async def keyboard_builder(user_id: int, group_id: int) -> InlineKeyboardMarkup:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM reddit_subscriptions WHERE group_id = ? AND receiver_id = ?;
            """,
            (group_id, user_id),
        ) as cursor:
            subreddits = await cursor.fetchall()

    keyboard = []
    for subreddit in subreddits:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"""{subreddit["subreddit_name"]} ({await utils.readable_time(int(dateparser.parse(subreddit["create_time"]).timestamp()))} ago)""",
                    callback_data=f"""unsubscribe_reddit:{subreddit["subreddit_name"]},{subreddit["receiver_id"]}""",
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


@api_key("REDDIT")
@triggers(["unsub"])
@example("/unsub Formula1")
@usage("/unsub [subreddit]")
@description("Unsubscribe from a subreddit for daily post notifications.")
async def list_reddit_subscriptions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    List all Reddit subscriptions for a user.
    """
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM reddit_subscriptions WHERE group_id = ? AND receiver_id = ?;
            """,
            (update.message.chat_id, update.message.from_user.id),
        ) as cursor:
            result = await cursor.fetchone()

    if not result:
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

    if query.from_user.id != int(user_id):
        await query.answer(
            "You can't remove subreddits from other users' subscriptions."
        )
        return

    async with get_db(write=True) as conn:
        await conn.execute(
            "DELETE FROM reddit_subscriptions WHERE subreddit_name = ? AND receiver_id = ?",
            (subreddit_name, user_id),
        )
        await conn.commit()

    await query.answer(f"Removed /r/{subreddit_name} from your watchlist.")
    await context.bot.edit_message_text(
        text="You are subscribed to the following subreddits in this group. Tap to remove:",
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        reply_markup=await keyboard_builder(int(user_id), query.message.chat.id),
    )


async def worker_reddit_subscriptions(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker function to scan dB and send posts.
    """
    collected_posts = []

    async def poster(group_id: int, user_id: int, subreddit_name: str) -> None:
        subreddit = await reddit.subreddit(subreddit_name)
        username = await utils.get_username(user_id, context)

        try:
            async for subreddit_submission in subreddit.hot(limit=3):
                if subreddit_submission.stickied:
                    continue

                try:
                    collected_posts.append(
                        {
                            "group_id": group_id,
                            "user_id": user_id,
                            "post_response": make_response(
                                subreddit_submission,
                                username,
                            ),
                        }
                    )
                    return
                except (NotFound, BadRequest, Redirect, Forbidden):
                    await context.bot.send_message(
                        group_id,
                        f"@{username}: removed /r/{subreddit_name} from your watchlist because it was deleted or banned.",
                        parse_mode=ParseMode.HTML,
                    )

                    async with get_db(write=True) as conn:
                        await conn.execute(
                            """
                            DELETE FROM reddit_subscriptions WHERE subreddit_name = ? AND receiver_id = ?;
                            """,
                            (subreddit_name, user_id),
                        )
                        await conn.commit()
        except Exception as e:
            logger.error(e)
            logger.error(f"Error in worker_reddit_subscriptions for {subreddit_name}")
            return

    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT * FROM reddit_subscriptions ORDER BY group_id;
            """
        ) as cursor:
            subscriptions = await cursor.fetchall()

    for row in subscriptions:
        await poster(row["group_id"], row["receiver_id"], row["subreddit_name"])

    tasks = []
    for post in collected_posts:
        tasks.append(
            asyncio.ensure_future(
                context.bot.send_message(
                    post["group_id"],
                    post["post_response"],
                    parse_mode=ParseMode.HTML,
                )
            )
        )

    await asyncio.gather(*tasks)
