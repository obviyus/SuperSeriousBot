"""Add the configurable search answer model."""


def upgrade(connection):
    connection.execute(
        """
        ALTER TABLE group_settings
        ADD COLUMN search_model TEXT DEFAULT 'openrouter/x-ai/grok-4.3'
        """
    )


def downgrade(connection):
    connection.execute("ALTER TABLE group_settings DROP COLUMN search_model")
