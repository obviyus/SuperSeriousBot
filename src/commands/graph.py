from networkx import DiGraph
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config.db import get_db
from utils.decorators import description, example, triggers, usage


@usage("/graph")
@example("/graph")
@triggers(["graph"])
@description("Get the social graph of this group.")
async def get_oldest_mention(chat_id: int) -> str | None:
    """Get the creation time of the oldest mention in the chat."""
    async with await get_db() as conn:
        async with conn.execute(
            """
            SELECT create_time FROM main.chat_mentions WHERE chat_id = ? ORDER BY create_time LIMIT 1;
            """,
            (chat_id,),
        ) as cursor:
            result = await cursor.fetchone()

    return result["create_time"] if result else None


async def get_social_graph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the social graph of this group."""
    if not update.message:
        return

    oldest_mention = await get_oldest_mention(update.message.chat_id)
    if not oldest_mention:
        await update.message.reply_text(
            text="This group has no recorded activity.", parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text(
        f"This group's social graph is available at: https://bot.superserio.us/vis/{update.message.chat_id}.html."
        f"\n\nBuilt using data since {oldest_mention[0]}.",
        parse_mode=ParseMode.HTML,
    )


@usage("/friends")
@example("/friends")
@triggers(["friends"])
@description("Get the strongest connected user to your account.")
async def get_friends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the strongest connected user to your account."""
    try:
        graph: DiGraph = context.bot_data.__getitem__(
            f"network_{update.message.chat_id}"
        )

        user_id = int(update.message.from_user.id)

        if not graph.has_node(user_id):
            await update.message.reply_text("You are not in this group's social graph.")
            return

        edges_incoming = sorted(
            graph.in_edges(user_id, data=True),
            key=lambda x: x[2].get("width", 0),
            reverse=True,
        )
        edges_outgoing = sorted(
            graph.out_edges(user_id, data=True),
            key=lambda x: x[2].get("width", 0),
            reverse=True,
        )

        text = f"From the social graph of <b>{update.message.chat.title}</b>:"

        try:
            text += "\n\nYou have the strongest connections to:"
            count = 0
            for edge in edges_outgoing:
                if edge[1] == user_id:
                    continue

                if count >= 3:
                    break
                count += 1

                text += (
                    f"\n<code>{edge[2]['width']:6}"
                    f" ⟶ {await utils.get_first_name(edge[1], context)}</code>"
                )
        except IndexError:
            pass

        try:
            text += f"\n\nYou have the strongest connections from:"
            count = 0
            for edge in edges_incoming[:3]:
                if edge[0] == user_id:
                    continue

                if count >= 3:
                    break
                count += 1

                text += (
                    f"\n<code>{edge[2]['width']:6}"
                    f" ← {await utils.get_first_name(edge[0], context)}</code>"
                )
        except IndexError:
            pass

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except KeyError as e:
        await update.message.reply_text("This group has no social graph yet.")
        return
