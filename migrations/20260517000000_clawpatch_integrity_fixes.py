"""Add integrity constraints for command race fixes."""


def upgrade(connection):
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS quote_db_chat_message_unique
        ON quote_db (chat_id, message_id)
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS object_store_key_nocase_unique
        ON object_store (key COLLATE NOCASE)
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS object_store_file_unique_id_unique
        ON object_store (file_unique_id)
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS highlights_chat_user_string_unique
        ON highlights (chat_id, user_id, string COLLATE NOCASE)
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS summon_groups_chat_name_unique
        ON summon_groups (chat_id, group_name COLLATE NOCASE)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX IF EXISTS summon_groups_chat_name_unique")
    connection.execute("DROP INDEX IF EXISTS highlights_chat_user_string_unique")
    connection.execute("DROP INDEX IF EXISTS object_store_file_unique_id_unique")
    connection.execute("DROP INDEX IF EXISTS object_store_key_nocase_unique")
    connection.execute("DROP INDEX IF EXISTS quote_db_chat_message_unique")
