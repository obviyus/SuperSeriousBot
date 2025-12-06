"""
This module contains a Caribou migration.

Migration Name: add_weather_cache
Migration Version: 20251206000000
"""


def upgrade(connection):
    # Weather Cache Table - stores user's last weather location lookup
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_cache (
            user_id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade(connection):
    connection.execute("DROP TABLE IF EXISTS weather_cache")
