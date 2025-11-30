"""
Add index for incoming mentions queries (who mentions a specific user).

AIDEV-NOTE: The existing idx_chat_mentions_network index is optimized for
outgoing queries (chat_id, mentioning_user_id, mentioned_user_id).
This new index optimizes incoming queries for the /friends command.
"""


def upgrade(connection):
    """Add index for incoming mention lookups."""
    # Index for "who mentions this user" queries
    # Covers: WHERE chat_id = ? AND mentioned_user_id = ?
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_mentions_incoming
        ON chat_mentions(chat_id, mentioned_user_id, mentioning_user_id);
    """)
    print("Added idx_chat_mentions_incoming index")


def downgrade(connection):
    """Remove the index."""
    connection.execute("DROP INDEX IF EXISTS idx_chat_mentions_incoming;")
    print("Removed idx_chat_mentions_incoming index")
