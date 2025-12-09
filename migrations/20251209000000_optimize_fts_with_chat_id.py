"""
This module contains a Caribou migration.

Migration Name: optimize_fts_with_chat_id
Migration Version: 20251209000000

AIDEV-NOTE: This migration rebuilds the FTS5 index to include chat_id as a filter column.
This allows FTS queries to filter by chat_id within the index itself, avoiding slow joins.
The 'chat_id UNINDEXED' means it's stored but not tokenized for text search.
"""


def upgrade(connection):
    # Drop existing trigger first
    connection.execute("DROP TRIGGER IF EXISTS chat_stats_ai")

    # Drop existing FTS table
    connection.execute("DROP TABLE IF EXISTS chat_stats_fts")

    # Recreate FTS table with chat_id as an unindexed column (for filtering, not searching)
    connection.execute(
        """
        CREATE VIRTUAL TABLE chat_stats_fts USING fts5(
            message_text,
            chat_id UNINDEXED,
            content='chat_stats',
            content_rowid='id'
        )
        """
    )

    # Recreate trigger to include chat_id
    connection.execute(
        """
        CREATE TRIGGER chat_stats_ai AFTER INSERT ON chat_stats BEGIN
            INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
            VALUES (new.id, new.message_text, new.chat_id);
        END
        """
    )

    # Rebuild the FTS index from existing data
    connection.execute(
        """
        INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
        SELECT id, message_text, chat_id FROM chat_stats
        """
    )


def downgrade(connection):
    # Drop trigger
    connection.execute("DROP TRIGGER IF EXISTS chat_stats_ai")

    # Drop new FTS table
    connection.execute("DROP TABLE IF EXISTS chat_stats_fts")

    # Recreate original FTS table without chat_id
    connection.execute(
        """
        CREATE VIRTUAL TABLE chat_stats_fts USING fts5(
            message_text,
            content='chat_stats',
            content_rowid='id'
        )
        """
    )

    # Recreate original trigger
    connection.execute(
        """
        CREATE TRIGGER chat_stats_ai AFTER INSERT ON chat_stats BEGIN
            INSERT INTO chat_stats_fts (rowid, message_text)
            VALUES (new.id, new.message_text);
        END
        """
    )

    # Rebuild the FTS index
    connection.execute(
        """
        INSERT INTO chat_stats_fts (rowid, message_text)
        SELECT id, message_text FROM chat_stats
        """
    )
