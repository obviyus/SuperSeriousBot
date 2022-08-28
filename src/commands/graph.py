from heapq import heappop, heappush

from pyvis.network import Network
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from utils.decorators import description, example, triggers, usage


@usage("/graph")
@example("/graph")
@triggers(["graph"])
@description("Get the social graph of this group.")
async def get_graph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the social graph of this group."""
    await update.message.reply_text(
        f"This group's social graph is available at: https://bot.superserio.us/{update.message.chat_id}.html",
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

        text = f"From the social graph of <b>{update.message.chat.title}</b>"

        try:
            strongest_from = heappop(edges_from)
            text += (
                f"- You have the strongest connection with @{await utils.get_username(strongest_from[1], context)} with"
                f" a strength of {-1 * strongest_from[0]}."
            )
        except IndexError:
            pass

        try:
            strongest_to = heappop(edges_to)
            text += (
                f"- \n\n@{await utils.get_username(strongest_to[1], context)} has the strongest connection to you with"
                f" a strength of {-1 * strongest_to[0]}."
            )
        except IndexError:
            pass

        await update.message.reply_text(text)
    except KeyError:
        await update.message.reply_text("This group has no social graph yet.")
        return
