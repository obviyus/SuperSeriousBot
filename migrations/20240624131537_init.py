"""
This module contains a Caribou migration.

Migration Name: initial_schema
Migration Version: 20240624131537
"""


def upgrade(connection):
    # Chat Statistics Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            message_id INTEGER,
            message_text TEXT
        )
    """
    )

    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chat_stats_fts USING fts5(
            message_text,
            content='chat_stats',
            content_rowid='id'
        )
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS chat_stats_chat_user_message_id_index
        ON chat_stats (chat_id, user_id, message_id)
    """
    )

    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS chat_stats_ai AFTER INSERT ON chat_stats BEGIN
            INSERT INTO chat_stats_fts (rowid, message_text)
            VALUES (new.id, new.message_text);
        END
    """
    )

    # Chat Mentions Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            mentioning_user_id INTEGER NOT NULL,
            mentioned_user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        )
    """
    )

    # Command Statistics Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS command_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command VARCHAR(255) NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # TV Show Notifications Tables
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tv_opt_in (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            chat_id VARCHAR(255) NOT NULL,
            username VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tv_notifications (
            id INTEGER PRIMARY KEY,
            user_id SIGNED INTEGER NOT NULL,
            show_id VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tv_shows (
            id INTEGER PRIMARY KEY,
            show_id VARCHAR(255) NOT NULL,
            show_name VARCHAR(255) NOT NULL,
            show_image VARCHAR(255) NOT NULL,
            next_episode_time INTEGER NULL,
            next_episode_name VARCHAR(255) NULL,
            sent INTEGER NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Reddit Subscriptions Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reddit_subscriptions (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            subreddit_name VARCHAR(255) NOT NULL,
            receiver_id INTEGER NOT NULL,
            receiver_username VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Object Store Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS object_store (
            id INTEGER PRIMARY KEY,
            file_id VARCHAR(255) NOT NULL,
            file_unique_id VARCHAR(255) NOT NULL,
            key VARCHAR(255) NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            type VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fetch_count INTEGER NOT NULL DEFAULT 0
        )
    """
    )

    # Quote DB Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_db (
            id INTEGER PRIMARY KEY,
            message_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_user_id INTEGER NOT NULL,
            saver_user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            forwarded_message_id INTEGER NULL
        )
    """
    )

    # Summon Groups Tables
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS summon_groups (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            group_name VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creator_id INTEGER NOT NULL
        )
    """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS summon_group_members (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Highlights Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS highlights (
            id INTEGER PRIMARY KEY,
            string VARCHAR(255) NOT NULL,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """
    )

    # YouTube Subscriptions Tables
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS youtube_subscriptions (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            channel_id VARCHAR(255) NOT NULL,
            latest_video_id VARCHAR(255) NOT NULL,
            creator_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS youtube_subscribers (
            id INTEGER PRIMARY KEY,
            subscription_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # User Command Limits Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_command_limits (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            command VARCHAR(255) NOT NULL,
            `limit` INTEGER NOT NULL,
            current_usage INTEGER NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Habit Tracking Tables
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS habit (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            habit_name VARCHAR(255) NOT NULL,
            weekly_goal INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creator_id INTEGER NOT NULL
        )
    """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS habit_members (
            habit_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habit(id),
            PRIMARY KEY (habit_id, user_id)
        )
    """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS habit_log (
            id INTEGER PRIMARY KEY,
            habit_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habit(id)
        )
    """
    )

    # Command Whitelist Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS command_whitelist (
            command VARCHAR(255) NOT NULL,
            whitelist_type VARCHAR(255) NOT NULL DEFAULT 'USER',
            whitelist_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (command, whitelist_type, whitelist_id)
        )
    """
    )

    # Reminders Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title VARCHAR(255) NOT NULL,
            target_time INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Steam Offers Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS steam_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            release_date TEXT,
            review_score TEXT,
            original_price TEXT,
            final_price TEXT,
            discount TEXT,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Group Settings Table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS group_settings (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0
        )
    """
    )

    # Create indexes
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS command_stats_user_id_command_index
        ON command_stats (command, user_id)
    """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS tv_opt_in_user_id_chat_id_index
        ON tv_opt_in (user_id, chat_id)
    """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS summon_groups_group_name_index
        ON summon_groups (group_name)
    """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS highlight_words_word_index
        ON highlights (string)
    """
    )


def downgrade(connection):
    # Drop all tables in reverse order
    tables = [
        "group_settings",
        "steam_offers",
        "reminders",
        "command_whitelist",
        "habit_log",
        "habit_members",
        "habit",
        "user_command_limits",
        "youtube_subscribers",
        "youtube_subscriptions",
        "highlights",
        "summon_group_members",
        "summon_groups",
        "quote_db",
        "object_store",
        "reddit_subscriptions",
        "tv_shows",
        "tv_notifications",
        "tv_opt_in",
        "command_stats",
        "chat_mentions",
        "chat_stats_fts",
        "chat_stats",
    ]
    for table in tables:
        connection.execute(f"DROP TABLE IF EXISTS {table}")

    # Drop indexes
    indexes = [
        "command_stats_user_id_command_index",
        "tv_opt_in_user_id_chat_id_index",
        "summon_groups_group_name_index",
        "highlight_words_word_index",
    ]
    for index in indexes:
        connection.execute(f"DROP INDEX IF EXISTS {index}")

    # Drop triggers
    connection.execute("DROP TRIGGER IF EXISTS chat_stats_ai")
