"""
This module contains a Caribou migration.

Migration Name: quote_recent_history
Migration Version: 20250713000000
"""


def upgrade(connection):
    # Quote Recent History Table - tracks recently shown quotes to prevent repetition
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_recent_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            quote_id INTEGER NOT NULL,
            shown_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quote_id) REFERENCES quote_db(id)
        )
        """
    )

    # Index for efficient cleanup and querying
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS quote_recent_history_chat_time_index 
        ON quote_recent_history (chat_id, shown_time)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX IF EXISTS quote_recent_history_chat_time_index")
    connection.execute("DROP TABLE IF EXISTS quote_recent_history")
