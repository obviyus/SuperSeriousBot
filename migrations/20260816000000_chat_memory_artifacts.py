"""Add precomputed chat memory artifacts."""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE chat_aliases (
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            alias TEXT NOT NULL, confidence REAL NOT NULL,
            update_time DATETIME NOT NULL,
            PRIMARY KEY (chat_id, alias)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE chat_personas (
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            sheet TEXT NOT NULL, receipts TEXT NOT NULL,
            source_end_message_id INTEGER NOT NULL,
            update_time DATETIME NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE chat_lore (
            chat_id INTEGER NOT NULL, topic TEXT NOT NULL,
            summary TEXT NOT NULL, receipts TEXT NOT NULL,
            source_end_message_id INTEGER NOT NULL,
            update_time DATETIME NOT NULL,
            PRIMARY KEY (chat_id, topic)
        )
        """
    )


def downgrade(connection):
    connection.execute("DROP TABLE chat_lore")
    connection.execute("DROP TABLE chat_personas")
    connection.execute("DROP TABLE chat_aliases")
