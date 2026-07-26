"""Add command usage history and failure context."""


def upgrade(connection):
    for definition in (
        "chat_id INTEGER",
        "message_id INTEGER",
        "username TEXT",
        "input_text TEXT",
        "status TEXT NOT NULL DEFAULT 'completed'",
        "duration_ms INTEGER",
        "error_type TEXT",
        "error_message TEXT",
        "error_traceback TEXT",
    ):
        connection.execute(f"ALTER TABLE command_stats ADD COLUMN {definition}")
    connection.execute(
        """
        CREATE INDEX command_stats_create_time_index
        ON command_stats (create_time)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX command_stats_create_time_index")
    for column in (
        "error_traceback",
        "error_message",
        "error_type",
        "duration_ms",
        "status",
        "input_text",
        "username",
        "message_id",
        "chat_id",
    ):
        connection.execute(f"ALTER TABLE command_stats DROP COLUMN {column}")
