"""Add configurable models for cron and song generation."""


def upgrade(connection):
    connection.execute(
        """
        ALTER TABLE group_settings
        ADD COLUMN cron_model TEXT DEFAULT 'openrouter/x-ai/grok-4.3'
        """
    )
    connection.execute(
        """
        ALTER TABLE group_settings
        ADD COLUMN song_model TEXT DEFAULT 'openrouter/x-ai/grok-4.3'
        """
    )


def downgrade(connection):
    connection.execute("ALTER TABLE group_settings DROP COLUMN song_model")
    connection.execute("ALTER TABLE group_settings DROP COLUMN cron_model")
