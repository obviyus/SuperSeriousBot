"""Add reply metadata and search observability."""


def upgrade(connection):
    for table, column in (
        ("chat_stats", "reply_to_message_id INTEGER"),
        ("chat_stats", "reply_to_user_id INTEGER"),
        ("user_stats", "first_name TEXT"),
    ):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
    connection.execute(
        """
        CREATE TABLE search_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL, answer_message_id INTEGER,
            question TEXT NOT NULL, answer TEXT NOT NULL, model TEXT NOT NULL,
            citation_message_ids TEXT NOT NULL,
            duration_ms INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX search_events_chat_time_index ON search_events (chat_id, create_time)"
    )
    connection.execute(
        """
        CREATE TABLE search_feedback (
            event_id INTEGER NOT NULL REFERENCES search_events(id),
            user_id INTEGER NOT NULL, vote INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, user_id)
        )
        """
    )


def downgrade(connection):
    connection.execute("DROP TABLE search_feedback")
    connection.execute("DROP INDEX search_events_chat_time_index")
    connection.execute("DROP TABLE search_events")
    connection.execute("ALTER TABLE user_stats DROP COLUMN first_name")
    connection.execute("ALTER TABLE chat_stats DROP COLUMN reply_to_user_id")
    connection.execute("ALTER TABLE chat_stats DROP COLUMN reply_to_message_id")
