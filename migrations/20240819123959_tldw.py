"""
This module contains a Caribou migration.

Migration Name: tldw 
Migration Version: 20240819123959
"""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tldw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id VARCHAR(255) NOT NULL,
                user_id INTEGER NOT NULL,
                summary TEXT,
                create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """
    )
    pass


def downgrade(connection):
    connection.execute("DROP TABLE tldw;")
    pass
