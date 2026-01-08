from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config import logger
from config.db import get_db
from utils.decorators import description, example, triggers, usage
from utils.messages import get_message


async def _get_top_connections(
    chat_id: int, user_id: int, limit: int = 3
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    Get top incoming and outgoing connections for a user directly from DB.

    AIDEV-NOTE: This queries only the specific user's connections instead of
    building the entire graph. For 1M+ message chats, this is O(user_edges)
    instead of O(all_edges). Uses covering index idx_chat_mentions_network.

    Returns:
        Tuple of (outgoing, incoming) where each is a list of (user_id, weight)
    """
    async with get_db() as conn:
        # Top outgoing: people this user mentions most
        async with conn.execute(
            """
            SELECT mentioned_user_id, COUNT(*) as weight
            FROM chat_mentions
            WHERE chat_id = ? AND mentioning_user_id = ? AND mentioned_user_id != ?
            GROUP BY mentioned_user_id
            ORDER BY weight DESC
            LIMIT ?
            """,
            (chat_id, user_id, user_id, limit),
        ) as cursor:
            outgoing = [
                (row["mentioned_user_id"], row["weight"])
                for row in await cursor.fetchall()
            ]

        # Top incoming: people who mention this user most
        async with conn.execute(
            """
            SELECT mentioning_user_id, COUNT(*) as weight
            FROM chat_mentions
            WHERE chat_id = ? AND mentioned_user_id = ? AND mentioning_user_id != ?
            GROUP BY mentioning_user_id
            ORDER BY weight DESC
            LIMIT ?
            """,
            (chat_id, user_id, user_id, limit),
        ) as cursor:
            incoming = [
                (row["mentioning_user_id"], row["weight"])
                for row in await cursor.fetchall()
            ]

    return outgoing, incoming


async def _user_has_connections(chat_id: int, user_id: int) -> bool:
    """Check if user has any connections in the chat's social graph."""
    # AIDEV-NOTE: Use UNION instead of OR for better index utilization.
    # Each branch can use its respective covering index.
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT 1 FROM chat_mentions
            WHERE chat_id = ? AND mentioning_user_id = ?
            UNION
            SELECT 1 FROM chat_mentions
            WHERE chat_id = ? AND mentioned_user_id = ?
            LIMIT 1
            """,
            (chat_id, user_id, chat_id, user_id),
        ) as cursor:
            return await cursor.fetchone() is not None


async def _chat_has_mentions(chat_id: int) -> bool:
    """Check if chat has any mentions recorded."""
    async with get_db() as conn:
        async with conn.execute(
            "SELECT 1 FROM chat_mentions WHERE chat_id = ? LIMIT 1",
            (chat_id,),
        ) as cursor:
            return await cursor.fetchone() is not None


@usage("/friends")
@example("/friends")
@triggers(["friends"])
@description("Get the strongest connected user to your account.")
async def get_friends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    """Get the strongest connected user to your account."""
    if not message.from_user:
        return

    try:
        chat_id = message.chat_id
        user_id = message.from_user.id

        # Quick check if chat has any data
        if not await _chat_has_mentions(chat_id):
            await message.reply_text("This group has no social graph yet.")
            return

        # Check if user is in the graph
        if not await _user_has_connections(chat_id, user_id):
            await message.reply_text("You are not in this group's social graph.")
            return

        # Get top 3 connections directly from DB (no full graph build)
        edges_outgoing, edges_incoming = await _get_top_connections(
            chat_id, user_id, limit=3
        )

        text = f"From the social graph of <b>{message.chat.title}</b>:"

        # Batch fetch names for better performance
        user_ids_to_fetch = {uid for uid, _ in edges_outgoing} | {
            uid for uid, _ in edges_incoming
        }

        # Pre-fetch all names in parallel
        name_tasks = {
            uid: utils.get_first_name(uid, context) for uid in user_ids_to_fetch
        }
        names = {}
        for uid, task in name_tasks.items():
            try:
                names[uid] = await task
            except Exception:
                names[uid] = str(uid)

        sections = [
            ("You have the strongest connections to:", "⟶", edges_outgoing),
            ("You have the strongest connections from:", "←", edges_incoming),
        ]
        for header, arrow, edges in sections:
            if not edges:
                continue
            text += f"\n\n{header}"
            for uid, weight in edges:
                text += f"\n<code>{weight:6} {arrow} {names.get(uid, str(uid))}</code>"

        await message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in get_friends: {e}")
        await message.reply_text("An error occurred while fetching your connections.")
        return
