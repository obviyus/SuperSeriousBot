"""
Add tldr_model column to group_settings table,
remove caption_model column (caption command removed).

AIDEV-NOTE: tldw command merged into tldr, so only tldr_model is needed.
"""


def upgrade(connection):
    # Add tldr_model column
    connection.execute("""
        ALTER TABLE group_settings
        ADD COLUMN tldr_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast'
    """)

    # Drop caption_model column by recreating table (SQLite limitation)
    connection.execute("""
        CREATE TABLE group_settings_new (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0,
            ask_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast',
            edit_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash-image-preview',
            tr_model TEXT DEFAULT 'google/gemini-2.5-flash',
            tldr_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast'
        )
    """)

    connection.execute("""
        INSERT INTO group_settings_new (
            chat_id, create_time, fts, steam_offers,
            ask_model, edit_model, tr_model, tldr_model
        )
        SELECT
            chat_id, create_time, fts, steam_offers,
            COALESCE(ask_model, 'openrouter/x-ai/grok-4-fast'),
            COALESCE(edit_model, 'openrouter/google/gemini-2.5-flash-image-preview'),
            COALESCE(tr_model, 'google/gemini-2.5-flash'),
            COALESCE(tldr_model, 'openrouter/x-ai/grok-4-fast')
        FROM group_settings
    """)

    connection.execute("DROP TABLE group_settings")
    connection.execute("ALTER TABLE group_settings_new RENAME TO group_settings")


def downgrade(connection):
    # Recreate table with caption_model column, remove tldr_model column
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
            'openrouter/x-ai/grok-4-fast',
            COALESCE(edit_model, 'openrouter/google/gemini-2.5-flash-image-preview'),
            COALESCE(tr_model, 'google/gemini-2.5-flash')
        FROM group_settings
    """)

    connection.execute("DROP TABLE group_settings")
    connection.execute("ALTER TABLE group_settings_new RENAME TO group_settings")
