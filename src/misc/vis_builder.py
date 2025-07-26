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
    
    # Fetch all mentions and filter self-references in DB query
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT mentioning_user_id AS source, mentioned_user_id AS target, COUNT(*) as count
            FROM chat_mentions 
            WHERE chat_id = ? AND mentioning_user_id != mentioned_user_id
            GROUP BY mentioning_user_id, mentioned_user_id;
            """,
            (chat_id,),
        ) as cursor:
            mentions = await cursor.fetchall()
    
    if not mentions:
        logger.info(f"No mentions found for chat_id: {chat_id}")
        return
    
    # Early exit for empty networks
    unique_users = set()
    edge_data = []
    
    for row in mentions:
        unique_users.add(row["source"])
        unique_users.add(row["target"])
        edge_data.append((row["source"], row["target"], row["count"]))
    
    # Batch fetch all user names
    user_names = await batch_get_user_names(unique_users, context)
    
    # Get chat title
    try:
        chat_title = f"Chat {(await context.bot.get_chat(chat_id)).title}"
    except (BadRequest, Forbidden):
        chat_title = f"Chat {chat_id}"
    
    # Create graph with bulk operations
    graph = nx.DiGraph()
    
    # Add all nodes at once
    nodes_with_labels = [(uid, {"label": user_names[uid]}) for uid in unique_users]
    graph.add_nodes_from(nodes_with_labels)
    
    # Add all edges at once
    edges_with_weights = [(src, tgt, {"weight": cnt}) for src, tgt, cnt in edge_data]
    graph.add_edges_from(edges_with_weights)
    
    # Create network visualization
    network = Network(
        heading=chat_title,
        height=1000,
        width=1000,
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
    network.save_graph(str(vis_dir / f"{chat_id}.html"))


async def worker_build_network(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker function to build a network for a chat.
    """
    # Get chats with mention counts to prioritize
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT chat_id, COUNT(*) as mention_count
            FROM chat_mentions
            WHERE mentioning_user_id != mentioned_user_id
            GROUP BY chat_id
            ORDER BY mention_count DESC;
            """
        ) as cursor:
            chats = await cursor.fetchall()
    
    if not chats:
        logger.info("No chats with mentions found")
        return
    
    # Process chats with concurrency limit
    # AIDEV-NOTE: Limit concurrent operations to prevent overwhelming the system
    semaphore = asyncio.Semaphore(5)
    
    async def process_chat(chat_id: str):
        async with semaphore:
            await generate_network_for_chat(chat_id, context)
    
    tasks = [process_chat(row["chat_id"]) for row in chats]
    await asyncio.gather(*tasks, return_exceptions=True)
