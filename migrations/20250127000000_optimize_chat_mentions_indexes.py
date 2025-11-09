"""
Add indexes to chat_mentions table for performance optimization.
"""

def upgrade(connection):
    """Add indexes for optimized queries."""
    # Index for get_oldest_mention query
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_mentions_chat_create
        ON chat_mentions(chat_id, create_time);
    """)

    # Composite index for network generation query
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_mentions_network
        ON chat_mentions(chat_id, mentioning_user_id, mentioned_user_id);
    """)

    # Index for counting mentions per chat
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_mentions_chat_count
        ON chat_mentions(chat_id)
        WHERE mentioning_user_id != mentioned_user_id;
    """)

    print("Added performance indexes to chat_mentions table")

def downgrade(connection):
    """Remove the indexes."""
    connection.execute("DROP INDEX IF EXISTS idx_chat_mentions_chat_create;")
    connection.execute("DROP INDEX IF EXISTS idx_chat_mentions_network;")
    connection.execute("DROP INDEX IF EXISTS idx_chat_mentions_chat_count;")
    print("Removed chat_mentions indexes")
