"""Index chat messages by chat and Telegram message ID."""


def upgrade(connection):
    connection.execute("""
        CREATE INDEX IF NOT EXISTS chat_stats_chat_message_id_index
        ON chat_stats (chat_id, message_id)
    """)


def downgrade(connection):
    connection.execute("DROP INDEX IF EXISTS chat_stats_chat_message_id_index")
