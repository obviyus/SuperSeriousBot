"""Add speaker-owned utterances to semantic chat search."""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE chat_search_utterances (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            start_message_id INTEGER NOT NULL,
            end_message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            message_count INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            embedding F32_BLOB(256) NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimension INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                chat_id,
                start_message_id,
                embedding_model,
                embedding_dimension
            )
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX chat_search_utterances_chat_idx
        ON chat_search_utterances (chat_id, embedding_model, embedding_dimension)
        """
    )
    connection.execute(
        """
        UPDATE group_settings
        SET search_model = 'openrouter/google/gemini-3-flash-preview'
        WHERE search_model IS NULL
        OR search_model IN (
            'openrouter/x-ai/grok-4.3',
            'openrouter/x-ai/grok-4.5',
            'x-ai/grok-4.5'
        )
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX IF EXISTS chat_search_utterances_chat_idx")
    connection.execute("DROP TABLE IF EXISTS chat_search_utterances")
