"""Index utterances by member for the chat memory build."""


def upgrade(connection):
    connection.execute(
        """
        CREATE INDEX chat_search_utterances_member_idx
        ON chat_search_utterances (chat_id, user_id, end_message_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX chat_search_utterances_range_idx
        ON chat_search_utterances (chat_id, end_message_id, start_message_id, user_id)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX chat_search_utterances_range_idx")
    connection.execute("DROP INDEX chat_search_utterances_member_idx")
