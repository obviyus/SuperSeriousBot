"""
Add ai_model column to group_settings table
"""


def upgrade(connection):
    connection.execute("""
        ALTER TABLE group_settings
        ADD COLUMN ai_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash'
    """)


def downgrade(connection):
    # SQLite doesn't support dropping columns directly
    connection.execute("""
        CREATE TABLE group_settings_new (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0
        )
    """)

    connection.execute("""
        INSERT INTO group_settings_new (chat_id, create_time, fts, steam_offers)
        SELECT chat_id, create_time, fts, steam_offers FROM group_settings
    """)

    connection.execute("DROP TABLE group_settings")
    connection.execute("ALTER TABLE group_settings_new RENAME TO group_settings")
