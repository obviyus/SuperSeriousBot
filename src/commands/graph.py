from networkx import DiGraph
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import utils
from config import logger
from utils.decorators import description, example, triggers, usage


@usage("/friends")
@example("/friends")
@triggers(["friends"])
@description("Get the strongest connected user to your account.")
async def get_friends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the strongest connected user to your account."""
    try:
        # AIDEV-NOTE: Direct dict access is faster than __getitem__
        graph: DiGraph = context.bot_data.get(f"network_{update.message.chat_id}")
        if not graph:
            await update.message.reply_text("This group has no social graph yet.")
            return

        user_id = int(update.message.from_user.id)

        if not graph.has_node(user_id):
            await update.message.reply_text("You are not in this group's social graph.")
            return

        # AIDEV-NOTE: Only fetch top 3 edges instead of sorting all
        # Using heap for O(n) complexity instead of O(n log n) sorting
        import heapq

        # Get top 3 incoming edges
        incoming_heap = []
        for edge in graph.in_edges(user_id, data=True):
            if edge[0] != user_id:  # Skip self-loops early
                width = edge[2].get("weight", 0)
                if len(incoming_heap) < 3:
                    heapq.heappush(incoming_heap, (width, edge))
                elif width > incoming_heap[0][0]:
                    heapq.heapreplace(incoming_heap, (width, edge))

        edges_incoming = [edge for _, edge in sorted(incoming_heap, reverse=True)]

        # Get top 3 outgoing edges
        outgoing_heap = []
        for edge in graph.out_edges(user_id, data=True):
            if edge[1] != user_id:  # Skip self-loops early
                width = edge[2].get("weight", 0)
                if len(outgoing_heap) < 3:
                    heapq.heappush(outgoing_heap, (width, edge))
                elif width > outgoing_heap[0][0]:
                    heapq.heapreplace(outgoing_heap, (width, edge))

        edges_outgoing = [edge for _, edge in sorted(outgoing_heap, reverse=True)]

        text = f"From the social graph of <b>{update.message.chat.title}</b>:"

        # AIDEV-NOTE: Batch fetch names for better performance
        user_ids_to_fetch = set()
        for edge in edges_outgoing:
            user_ids_to_fetch.add(edge[1])
        for edge in edges_incoming:
            user_ids_to_fetch.add(edge[0])

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

        if edges_outgoing:
            text += "\n\nYou have the strongest connections to:"
            for edge in edges_outgoing:
                text += (
                    f"\n<code>{edge[2]['weight']:6}"
                    f" ⟶ {names.get(edge[1], str(edge[1]))}</code>"
                )

        if edges_incoming:
            text += "\n\nYou have the strongest connections from:"
            for edge in edges_incoming:
                text += (
                    f"\n<code>{edge[2]['weight']:6}"
                    f" ← {names.get(edge[0], str(edge[0]))}</code>"
                )

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        # AIDEV-NOTE: Catch all exceptions to prevent crashes
        logger.error(f"Error in get_friends: {e}")
        await update.message.reply_text(
            "An error occurred while fetching your connections."
        )
        return
