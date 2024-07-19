"""
This module contains a Caribou migration.

Migration Name: summon_pk 
Migration Version: 20240719174601
"""


def upgrade(connection):
    cursor = connection.cursor()

    # Remove duplicate entries
    cursor.execute(
        """
        DELETE FROM summon_group_members
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM summon_group_members
            GROUP BY group_id, user_id
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE new_summon_group_members (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (group_id, user_id)
        )
        """
    )

    # Copy data from the old table to the new table
    cursor.execute(
        """
        INSERT INTO new_summon_group_members (group_id, user_id, create_time)
        SELECT group_id, user_id, create_time
        FROM summon_group_members
        """
    )

    cursor.execute("DROP TABLE summon_group_members")
    cursor.execute(
        "ALTER TABLE new_summon_group_members RENAME TO summon_group_members"
    )

    connection.commit()


def downgrade(connection):
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE new_summon_group_members (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
    )

    cursor.execute(
        """
        INSERT INTO new_summon_group_members (group_id, user_id, create_time)
        SELECT group_id, user_id, create_time
        FROM summon_group_members
        """
    )

    cursor.execute("DROP TABLE summon_group_members")
    cursor.execute(
        "ALTER TABLE new_summon_group_members RENAME TO summon_group_members"
    )
    cursor.execute("DROP INDEX IF EXISTS idx_summon_group_members_group_user")

    connection.commit()
