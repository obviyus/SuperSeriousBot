"""
Migration Name: user_command_limits_unique
Migration Version: 20260710000000
"""


def upgrade(connection):
    connection.execute(
        """
        DELETE FROM user_command_limits
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM user_command_limits
            GROUP BY user_id, command
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS user_command_limits_user_command_unique
        ON user_command_limits (user_id, command)
        """
    )


def downgrade(connection):
    connection.execute(
        "DROP INDEX IF EXISTS user_command_limits_user_command_unique"
    )
