"""
This module contains a Caribou migration.

Migration Name: chat_semantic_search
Migration Version: 20260607000000
"""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_search_windows (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            start_message_id INTEGER NOT NULL,
            end_message_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            message_count INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            embedding F32_BLOB(1024) NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimension INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                chat_id,
                start_message_id,
                end_message_id,
                embedding_model,
                embedding_dimension
            )
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS chat_search_windows_chat_range_idx
        ON chat_search_windows (chat_id, start_message_id, end_message_id)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX IF EXISTS chat_search_windows_chat_range_idx")
    connection.execute("DROP TABLE IF EXISTS chat_search_windows")
