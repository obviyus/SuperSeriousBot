"""
This module contains a Caribou migration.

Migration Name: user_stats 
Migration Version: 20240917172646
"""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE user_stats (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            last_seen DATETIME,
            last_message_link TEXT
        );
        """
    )


def downgrade(connection):
    connection.execute("DROP TABLE user_stats;")
