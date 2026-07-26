"""Add retry-safe reminder delivery state."""


def upgrade(connection):
    connection.execute("ALTER TABLE reminders ADD COLUMN claim_time INTEGER")
    connection.execute(
        "ALTER TABLE reminders ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
    )
    connection.execute("ALTER TABLE reminders ADD COLUMN last_error TEXT")
    connection.execute(
        """
        CREATE INDEX reminders_due_claim_index
        ON reminders (target_time, claim_time)
        """
    )


def downgrade(connection):
    connection.execute("DROP INDEX reminders_due_claim_index")
    connection.execute("ALTER TABLE reminders DROP COLUMN last_error")
    connection.execute("ALTER TABLE reminders DROP COLUMN attempt_count")
    connection.execute("ALTER TABLE reminders DROP COLUMN claim_time")
