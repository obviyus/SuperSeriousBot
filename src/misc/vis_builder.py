import asyncio
import os
from collections import defaultdict

from pyvis.network import Network
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

import utils
from config import logger
from config.db import sqlite_conn


async def title_for_node(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        return await utils.get_first_name(user_id, context)
    except BadRequest:
        return f"{user_id}"


async def generate_network_for_chat(
    chat_id: str, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Generate a JSON file of nodes and edges for a chat. This data will be
    fed into vis.js to generate a graph.
    """

    logger.info(f"Generating network for chat_id: {chat_id}")
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT mentioning_user_id AS source, mentioned_user_id AS target
        FROM chat_mentions WHERE chat_id = ?;
        """,
        (chat_id,),
    )

    try:
        chat_title = f"Chat {(await context.bot.get_chat(chat_id)).title}"
    except (BadRequest, Forbidden):
        chat_title = f"Chat {chat_id}"

    network = Network(
        heading=chat_title,
        height=1000,
        width=1000,
    )

    mappings = defaultdict(lambda: defaultdict(int))
    user_id_to_name = {}

    for row in cursor.fetchall():
        mappings[row["source"]][row["target"]] += 1
        if row["source"] not in user_id_to_name:
            user_id_to_name[row["source"]] = await title_for_node(
                row["source"], context
            )
        if row["target"] not in user_id_to_name:
            user_id_to_name[row["target"]] = await title_for_node(
                row["target"], context
            )

    for source, targets in mappings.items():
        for target, count in targets.items():
            network.add_node(source, label=user_id_to_name[source])
            network.add_node(target, label=user_id_to_name[target])

            logger.info(f"Adding edge from {source} to {target} with weight {count}")
            network.add_edge(source, target, value=count)

    logger.info(
        f"Finished generating a network with {len(network.nodes)} nodes and {len(network.edges)} edges"
    )

    # Make directory if it doesn't exist
    if not os.path.exists(f"{os.getcwd()}/vis"):
        os.mkdir(f"{os.getcwd()}/vis")

    network.set_options(
        """"const options = {
  "physics": {
    "solver": "forceAtlas2Based",
    "forceAtlas2Based": {
      "gravitationalConstant": -500,
      "springLength": 305
    }
  }
}"""
    )
    network.save_graph(f"vis/{chat_id}.html")


async def worker_build_network(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker function to build a network for a chat.
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT chat_id FROM chat_mentions;
        """
    )

    tasks = []

    for row in cursor.fetchall():
        tasks.append(
            asyncio.ensure_future(generate_network_for_chat(row["chat_id"], context))
        )

    await asyncio.gather(*tasks)
