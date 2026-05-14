"""Add auto download setting to groups."""


def upgrade(connection):
    connection.execute(
        """
        ALTER TABLE group_settings
        ADD COLUMN auto_dl TINYINT NOT NULL DEFAULT 0
        """
    )


def downgrade(connection):
    connection.execute(
        """
        CREATE TABLE group_settings_new (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0,
            ask_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast',
            edit_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash-image-preview',
            tr_model TEXT DEFAULT 'google/gemini-2.5-flash',
            tldr_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast',
            ask_thinking TEXT DEFAULT 'none'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO group_settings_new (
            chat_id, create_time, fts, steam_offers,
            ask_model, edit_model, tr_model, tldr_model, ask_thinking
        )
        SELECT
            chat_id, create_time, fts, steam_offers,
            ask_model, edit_model, tr_model, tldr_model, ask_thinking
        FROM group_settings
        """
    )
    connection.execute("DROP TABLE group_settings")
    connection.execute("ALTER TABLE group_settings_new RENAME TO group_settings")
