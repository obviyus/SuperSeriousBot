"""
This module contains a Caribou migration.

Migration Name: command_blocklist
Migration Version: 20241209165053
"""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE command_blocklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            command TEXT NOT NULL,
            blocked_by INTEGER NOT NULL,
            blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, command)
        );
        """,
    )


def downgrade(connection):
    connection.execute("DROP TABLE command_blocklist;")
