"""
This module contains a Caribou migration.

Migration Name: steam_offer_notify 
Migration Version: 20240627091908
"""


def upgrade(connection):
    connection.execute(
        """
        ALTER TABLE steam_offers ADD COLUMN notified BOOLEAN DEFAULT FALSE;
        """
    )


def downgrade(connection):
    connection.execute(
        """
        ALTER TABLE steam_offers DROP COLUMN notified;
        """
    )
