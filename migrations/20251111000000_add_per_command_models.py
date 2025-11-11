"""
Add per-command AI model columns to group_settings table
"""


def upgrade(connection):
    # Add new columns for each command with appropriate defaults
    connection.execute("""
        ALTER TABLE group_settings
        ADD COLUMN ask_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast'
    """)

    connection.execute("""
        ALTER TABLE group_settings
        ADD COLUMN caption_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast'
    """)

    connection.execute("""
        ALTER TABLE group_settings
        ADD COLUMN edit_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash-image-preview'
    """)

    connection.execute("""
        ALTER TABLE group_settings
        ADD COLUMN tr_model TEXT DEFAULT 'google/gemini-2.5-flash'
    """)

    # Migrate existing ai_model value to ask_model for existing rows
    connection.execute("""
        UPDATE group_settings
        SET ask_model = ai_model
        WHERE ai_model IS NOT NULL AND ai_model != 'openrouter/google/gemini-2.5-flash'
    """)

    # Drop old ai_model column by recreating table (SQLite limitation)
    connection.execute("""
        CREATE TABLE group_settings_new (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0,
            ask_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast',
            caption_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast',
            edit_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash-image-preview',
            tr_model TEXT DEFAULT 'google/gemini-2.5-flash'
        )
    """)

    connection.execute("""
        INSERT INTO group_settings_new (
            chat_id, create_time, fts, steam_offers,
            ask_model, caption_model, edit_model, tr_model
        )
        SELECT
            chat_id, create_time, fts, steam_offers,
            COALESCE(ask_model, 'openrouter/x-ai/grok-4-fast'),
            COALESCE(caption_model, 'openrouter/x-ai/grok-4-fast'),
            COALESCE(edit_model, 'openrouter/google/gemini-2.5-flash-image-preview'),
            COALESCE(tr_model, 'google/gemini-2.5-flash')
        FROM group_settings
    """)

    connection.execute("DROP TABLE group_settings")
    connection.execute("ALTER TABLE group_settings_new RENAME TO group_settings")


def downgrade(connection):
    # Recreate table with ai_model column
    connection.execute("""
        CREATE TABLE group_settings_new (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0,
            ai_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash'
        )
    """)

    # Migrate ask_model back to ai_model
    connection.execute("""
        INSERT INTO group_settings_new (chat_id, create_time, fts, steam_offers, ai_model)
        SELECT chat_id, create_time, fts, steam_offers, ask_model FROM group_settings
    """)

    connection.execute("DROP TABLE group_settings")
    connection.execute("ALTER TABLE group_settings_new RENAME TO group_settings")
