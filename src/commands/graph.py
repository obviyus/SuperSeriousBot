import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config import logger
from config.db import get_db
from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["friends"],
    usage="/friends",
    example="/friends",
    description="Get the strongest connected user to your account.",
)
async def get_friends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return

    try:
        chat_id = message.chat_id
        user_id = message.from_user.id

        async with get_db() as conn:
            async with conn.execute(
                "SELECT 1 FROM chat_mentions WHERE chat_id = ? LIMIT 1",
                (chat_id,),
            ) as cursor:
                if await cursor.fetchone() is None:
                    await message.reply_text("This group has no social graph yet.")
                    return

            async with conn.execute(
                """
                SELECT 1 FROM chat_mentions
                WHERE chat_id = ?
                  AND (
                    (mentioning_user_id = ? AND mentioned_user_id != ?)
                    OR (mentioned_user_id = ? AND mentioning_user_id != ?)
                  )
                LIMIT 1
                """,
                (chat_id, user_id, user_id, user_id, user_id),
            ) as cursor:
                if await cursor.fetchone() is None:
                    await message.reply_text("You are not in this group's social graph.")
                    return

            async with conn.execute(
                """
                SELECT mentioned_user_id, COUNT(*) as weight
                FROM chat_mentions
                WHERE chat_id = ? AND mentioning_user_id = ? AND mentioned_user_id != ?
                GROUP BY mentioned_user_id
                ORDER BY weight DESC
                LIMIT 3
                """,
                (chat_id, user_id, user_id),
            ) as cursor:
                edges_outgoing = [
                    (row["mentioned_user_id"], row["weight"])
                    for row in await cursor.fetchall()
                ]

            async with conn.execute(
                """
                SELECT mentioning_user_id, COUNT(*) as weight
                FROM chat_mentions
                WHERE chat_id = ? AND mentioned_user_id = ? AND mentioning_user_id != ?
                GROUP BY mentioning_user_id
                ORDER BY weight DESC
                LIMIT 3
                """,
                (chat_id, user_id, user_id),
            ) as cursor:
                edges_incoming = [
                    (row["mentioning_user_id"], row["weight"])
                    for row in await cursor.fetchall()
                ]

        user_ids = list({uid for uid, _ in edges_outgoing} | {uid for uid, _ in edges_incoming})
        names: dict[int, str] = {}
        if user_ids:
            resolved_names = await asyncio.gather(
                *(utils.get_first_name(uid, context) for uid in user_ids),
                return_exceptions=True,
            )
            names = {
                uid: name if isinstance(name, str) else str(uid)
                for uid, name in zip(user_ids, resolved_names, strict=True)
            }

        text = f"From the social graph of <b>{message.chat.title}</b>:"
        for header, arrow, edges in (
            ("You have the strongest connections to:", "⟶", edges_outgoing),
            ("You have the strongest connections from:", "←", edges_incoming),
        ):
            if not edges:
                continue
            text += f"\n\n{header}"
            for uid, weight in edges:
                text += f"\n<code>{weight:6} {arrow} {names.get(uid, str(uid))}</code>"

        await message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in get_friends: {e}")
        await message.reply_text("An error occurred while fetching your connections.")
