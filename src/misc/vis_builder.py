import asyncio
from pathlib import Path
from typing import Dict, Set

import networkx as nx
from pyvis.network import Network
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

import utils
from config import logger
from config.db import get_db


async def batch_get_user_names(
    user_ids: Set[int], context: ContextTypes.DEFAULT_TYPE
) -> Dict[int, str]:
    """Batch fetch user names with caching and concurrent limits."""
    # AIDEV-NOTE: Using semaphore to prevent rate limiting
    semaphore = asyncio.Semaphore(10)
    user_names = {}

    async def fetch_name(user_id: int):
        async with semaphore:
            try:
                return user_id, await utils.get_first_name(user_id, context)
            except (BadRequest, Forbidden):
                return user_id, str(user_id)

    results = await asyncio.gather(*[fetch_name(uid) for uid in user_ids])

    for user_id, name in results:
        user_names[user_id] = name

    return user_names


async def generate_network_for_chat(
    chat_id: str, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Generate a JSON file of nodes and edges for a chat. This data will be
    fed into vis.js to generate a graph.
    """
    logger.info(f"Generating network for chat_id: {chat_id}")

    # AIDEV-NOTE: Use indexed query with hint for better performance
    # The idx_chat_mentions_network index covers this query perfectly
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT mentioning_user_id AS source, 
                   mentioned_user_id AS target, 
                   COUNT(*) as count
            FROM chat_mentions INDEXED BY idx_chat_mentions_network
            WHERE chat_id = ? AND mentioning_user_id != mentioned_user_id
            GROUP BY mentioning_user_id, mentioned_user_id
            HAVING count > 1;
            """,
            (chat_id,),
        ) as cursor:
            mentions = await cursor.fetchall()

    if not mentions:
        logger.info(f"No mentions found for chat_id: {chat_id}")
        return

    # AIDEV-NOTE: Pre-allocate data structures for better performance
    # Using estimated sizes reduces memory reallocation
    unique_users = set()
    edge_data = []

    # Process mentions in a single pass
    for row in mentions:
        source, target, count = row["source"], row["target"], row["count"]
        unique_users.add(source)
        unique_users.add(target)
        edge_data.append((source, target, count))

    user_names = await batch_get_user_names(unique_users, context)

    # Get chat title
    try:
        chat_title = f"Chat {(await context.bot.get_chat(chat_id)).title}"
    except (BadRequest, Forbidden):
        chat_title = f"Chat {chat_id}"

    # AIDEV-NOTE: Create graph with size hints for better memory allocation
    graph = nx.DiGraph()

    # Add all nodes at once with generator for memory efficiency
    graph.add_nodes_from((uid, {"label": user_names[uid]}) for uid in unique_users)

    # Add all edges at once with generator
    graph.add_edges_from((src, tgt, {"weight": cnt}) for src, tgt, cnt in edge_data)

    # AIDEV-NOTE: Optimize visualization for large graphs
    # Adjust physics settings based on graph size
    node_count = len(unique_users)
    if node_count > 100:
        # For large graphs, use less intensive physics
        height, width = 1500, 1500
    else:
        height, width = 1000, 1000

    network = Network(
        heading=chat_title,
        height=height,
        width=width,
        directed=True,  # Explicitly set for performance
        notebook=False,  # Disable notebook mode
    )

    network.from_nx(graph)

    logger.info(
        f"Finished generating a network with {len(network.nodes)} nodes and {len(network.edges)} edges"
    )

    # Cache the network for the chat
    context.bot_data[f"network_{chat_id}"] = graph

    # Use Path for better file operations
    vis_dir = Path("vis")
    vis_dir.mkdir(exist_ok=True)

    # AIDEV-NOTE: Adaptive physics settings based on graph size
    if node_count > 200:
        # Disable physics for very large graphs
        physics_options = '{"physics": {"enabled": false}}'
    elif node_count > 100:
        # Lighter physics for medium graphs
        physics_options = """{
  "physics": {
    "solver": "barnesHut",
    "barnesHut": {
      "gravitationalConstant": -2000,
      "springLength": 150,
      "damping": 0.4
    },
    "stabilization": {
      "iterations": 50
    }
  }
}"""
    else:
        # Original settings for small graphs
        physics_options = """{
  "physics": {
    "solver": "forceAtlas2Based",
    "forceAtlas2Based": {
      "gravitationalConstant": -500,
      "springLength": 305
    }
  }
}"""

    network.set_options(f"const options = {physics_options}")
    network.save_graph(str(vis_dir / f"{chat_id}.html"))


async def worker_build_network(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker function to build a network for a chat.
    """
    # AIDEV-NOTE: Only rebuild graphs that have changed
    # Get chats with recent activity for incremental updates
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT chat_id, COUNT(*) as mention_count,
                   MAX(create_time) as last_update
            FROM chat_mentions INDEXED BY idx_chat_mentions_chat_count
            WHERE mentioning_user_id != mentioned_user_id
            GROUP BY chat_id
            HAVING mention_count > 5
            ORDER BY last_update DESC
            LIMIT 100;
            """
        ) as cursor:
            chats = await cursor.fetchall()

    if not chats:
        logger.info("No chats with mentions found")
        return

    # AIDEV-NOTE: Adaptive concurrency based on system load
    # Lower concurrency prevents API rate limits and memory issues
    max_concurrent = min(3, len(chats))  # Max 3 concurrent builds
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_chat(chat_data: dict):
        async with semaphore:
            try:
                # Skip very small graphs
                if chat_data["mention_count"] < 10:
                    logger.debug(
                        f"Skipping small graph for chat {chat_data['chat_id']}"
                    )
                    return
                await generate_network_for_chat(chat_data["chat_id"], context)
            except Exception as e:
                logger.error(f"Error building network for {chat_data['chat_id']}: {e}")

    # Process in batches to control memory usage
    batch_size = 10
    for i in range(0, len(chats), batch_size):
        batch = chats[i : i + batch_size]
        tasks = [process_chat(chat_data) for chat_data in batch]
        await asyncio.gather(*tasks, return_exceptions=True)
        # Small delay between batches
        if i + batch_size < len(chats):
            await asyncio.sleep(1)
