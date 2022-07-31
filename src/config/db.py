import sqlite3

import redis

sqlite_conn = sqlite3.connect(
    "/db/SuperSeriousBot.db", check_same_thread=False, isolation_level=None
)
sqlite_conn.row_factory = sqlite3.Row

redis = redis.StrictRedis(
    host="redis", port=6379, db=0, decode_responses=True, charset="utf-8"
)

cursor = sqlite_conn.cursor()

# Chat Statistics Table
cursor.execute(
    f"""
    CREATE TABLE IF NOT EXISTS chat_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL
    )
    """
)

# Bot command statistics table
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS command_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command VARCHAR(255) NOT NULL,
        user_id INTEGER NOT NULL,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
)


# Table for TV Show Notifications
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `tv_opt_in` (
        `id` INTEGER PRIMARY KEY,
        `user_id` INTEGER NOT NULL,
        `chat_id` VARCHAR(255) NOT NULL,
        `username` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `tv_notifications` (
        `id` INTEGER PRIMARY KEY,
        `user_id` SIGNED INTEGER NOT NULL,
        `show_id` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `tv_shows` (
        `id` INTEGER PRIMARY KEY,
        `show_id` VARCHAR(255) NOT NULL,
        `show_name` VARCHAR(255) NOT NULL,
        `show_image` VARCHAR(255) NOT NULL,
        `next_episode_time` INTEGER NULL,
        `next_episode_name` VARCHAR(255) NULL,
        `sent` INTEGER NOT NULL DEFAULT 0,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

# Table for Reddit Subscriptions
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `reddit_subscriptions` (
        `id` INTEGER PRIMARY KEY,
        `group_id` INTEGER NOT NULL,
        `subreddit_name` VARCHAR(255) NOT NULL,
        `receiver_id` INTEGER NOT NULL,
        `receiver_username` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

# Table for object store
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `object_store` (
        `id` INTEGER PRIMARY KEY,
        `file_id` VARCHAR(255) NOT NULL,
        `file_unique_id` VARCHAR(255) NOT NULL,
        `key` VARCHAR(255) NOT NULL UNIQUE,
        `user_id` INTEGER NOT NULL,
        `type` VARCHAR(255) NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

# Table for Quote DB
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS `quote_db` (
        `id` INTEGER PRIMARY KEY,
        `message_id` INTEGER NOT NULL,
        `chat_id` INTEGER NOT NULL,
        `message_user_id` INTEGER NOT NULL,
        `saver_user_id` INTEGER NOT NULL,
        `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)
