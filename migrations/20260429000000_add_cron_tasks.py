"""
Add durable cron tasks.
"""


def upgrade(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS cron_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            task TEXT NOT NULL,
            cron_expr TEXT NOT NULL,
            timezone TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS cron_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cron_task_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            result_text TEXT,
            error_text TEXT,
            start_time DATETIME NOT NULL,
            finish_time DATETIME NOT NULL,
            FOREIGN KEY (cron_task_id) REFERENCES cron_tasks(id)
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS cron_tasks_enabled_index
        ON cron_tasks(enabled, chat_id, user_id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS cron_runs_task_id_desc_index
        ON cron_runs(cron_task_id, id DESC)
    """)


def downgrade(connection):
    connection.execute("DROP INDEX IF EXISTS cron_runs_task_id_desc_index")
    connection.execute("DROP INDEX IF EXISTS cron_tasks_enabled_index")
    connection.execute("DROP TABLE IF EXISTS cron_runs")
    connection.execute("DROP TABLE IF EXISTS cron_tasks")
