"""Add football fixtures and chat subscriptions."""


def upgrade(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS football_fixtures (
            provider_id TEXT PRIMARY KEY,
            competition TEXT NOT NULL,
            competition_name TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff_time INTEGER NOT NULL,
            status TEXT NOT NULL,
            alert_time INTEGER,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS football_fixtures_due_index
        ON football_fixtures (status, alert_time, kickoff_time)
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS football_alert_members (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS football_alert_deliveries (
            provider_id TEXT NOT NULL,
            kickoff_time INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            delivery_time INTEGER NOT NULL,
            PRIMARY KEY (provider_id, kickoff_time, chat_id, user_id)
        )
    """)


def downgrade(connection):
    connection.execute("DROP TABLE IF EXISTS football_alert_deliveries")
    connection.execute("DROP TABLE IF EXISTS football_alert_members")
    connection.execute("DROP INDEX IF EXISTS football_fixtures_due_index")
    connection.execute("DROP TABLE IF EXISTS football_fixtures")
