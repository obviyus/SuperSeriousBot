"""
This module contains a Caribou migration.

Migration Name: video_history
Migration Version: 20240624132855
"""


def upgrade(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS video_history (
                subscription_id INTEGER,
                video_id TEXT,
                status TEXT,
                create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (subscription_id, video_id)
            );
        """
    )
    pass


def downgrade(connection):
    connection.execute("DROP TABLE video_history;")
    pass
