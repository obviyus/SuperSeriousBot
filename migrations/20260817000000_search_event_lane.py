"""Record the search-answer lane."""


def upgrade(connection):
    connection.execute(
        "ALTER TABLE search_events ADD COLUMN lane TEXT NOT NULL DEFAULT 'fact'"
    )


def downgrade(connection):
    connection.execute("ALTER TABLE search_events DROP COLUMN lane")
