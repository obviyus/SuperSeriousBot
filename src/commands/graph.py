from heapq import heappop, heappush

from pyvis.network import Network
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


@usage("/graph")
@example("/graph")
@triggers(["graph"])
@description("Get the social graph of this group.")
async def get_graph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the social graph of this group."""
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT create_time FROM main.chat_mentions WHERE chat_id = ? ORDER BY create_time LIMIT 1;
        """,
        (update.message.chat_id,),
    )

    oldest_mention = cursor.fetchone()
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
        network: Network = context.bot_data.__getitem__(
            f"network_{update.message.chat_id}"
        )

        user_id = int(update.message.from_user.id)

        user_node = next(node for node in network.nodes if node["id"] == user_id)
        if not user_node:
            await update.message.reply_text("You are not in this group's social graph.")
            return

        edges_from, edges_to = [], []
        for edge in network.edges:
            if edge["from"] == user_id:
                heappush(edges_from, (-1 * edge["value"], edge["to"]))
            if edge["to"] == user_id:
                heappush(edges_to, (-1 * edge["value"], edge["from"]))

        text = f"From the social graph of <b>{update.message.chat.title}</b>:"

        try:
            text += "\n\nYou have the strongest connections with:"
            for _ in range(3):
                strongest_connection = heappop(edges_from)
                text += (
                    f"\n<code>{strongest_connection[0] * -1:6}"
                    f" ⟶ {await utils.get_first_name(strongest_connection[1], context)}</code>"
                )
        except IndexError:
            pass

        try:
            text += f"\n\nYou have the strongest connections from:"
            for _ in range(3):
                strongest_connection = heappop(edges_to)
                text += (
                    f"\n<code>{strongest_connection[0] * -1:6}"
                    f" ⟶ {await utils.get_first_name(strongest_connection[1], context)}</code>"
                )
        except IndexError:
            pass

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except KeyError:
        await update.message.reply_text("This group has no social graph yet.")
        return
