"""Index incoming mentions by message for the chat memory build."""


def upgrade(connection):
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_mentions_incoming_message
        ON chat_mentions (chat_id, mentioned_user_id, message_id)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX idx_chat_mentions_incoming_message")
