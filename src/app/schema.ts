import { Effect } from "telly";

import type { Database } from "./database.ts";

const statements = [
  `CREATE TABLE IF NOT EXISTS command_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    chat_id INTEGER,
    message_id INTEGER,
    username TEXT,
    input_text TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    duration_ms INTEGER,
    error_type TEXT,
    error_message TEXT,
    error_traceback TEXT
  )`,
  `CREATE INDEX IF NOT EXISTS command_stats_user_id_command_index
    ON command_stats (command, user_id)`,
  `CREATE INDEX IF NOT EXISTS command_stats_create_time_index
    ON command_stats (create_time)`,
  `CREATE TABLE IF NOT EXISTS command_blocklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    blocked_by INTEGER NOT NULL,
    blocked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, command)
  )`,
  `CREATE TABLE IF NOT EXISTS command_whitelist (
    command TEXT NOT NULL,
    whitelist_type TEXT NOT NULL DEFAULT 'user',
    whitelist_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (command, whitelist_type, whitelist_id)
  )`,
  `CREATE TABLE IF NOT EXISTS weather_cache (
    user_id INTEGER PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  )`,
  `CREATE TABLE IF NOT EXISTS group_settings (
    chat_id INTEGER PRIMARY KEY,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fts INTEGER NOT NULL DEFAULT 0,
    ask_model TEXT,
    edit_model TEXT,
    tr_model TEXT,
    tldr_model TEXT,
    ask_thinking TEXT,
    auto_dl INTEGER NOT NULL DEFAULT 0,
    search_model TEXT,
    cron_model TEXT,
    song_model TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS user_stats (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    first_name TEXT,
    last_seen DATETIME,
    last_message_link TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS chat_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    message_id INTEGER,
    message_text TEXT,
    reply_to_message_id INTEGER,
    reply_to_user_id INTEGER
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS chat_stats_chat_user_message_id_index
    ON chat_stats (chat_id, user_id, message_id)`,
  `CREATE INDEX IF NOT EXISTS chat_stats_chat_message_id_index
    ON chat_stats (chat_id, message_id)`,
  `CREATE VIRTUAL TABLE IF NOT EXISTS chat_stats_fts USING fts5(
    message_text,
    chat_id UNINDEXED,
    content='chat_stats',
    content_rowid='id'
  )`,
  `CREATE TRIGGER IF NOT EXISTS chat_stats_ai AFTER INSERT ON chat_stats BEGIN
    INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
    VALUES (new.id, new.message_text, new.chat_id);
  END`,
  `CREATE TABLE IF NOT EXISTS chat_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mentioning_user_id INTEGER NOT NULL,
    mentioned_user_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS idx_chat_mentions_network
    ON chat_mentions (chat_id, mentioning_user_id, mentioned_user_id)`,
  `CREATE INDEX IF NOT EXISTS idx_chat_mentions_incoming
    ON chat_mentions (chat_id, mentioned_user_id, mentioning_user_id)`,
  `CREATE TABLE IF NOT EXISTS object_store (
    id INTEGER PRIMARY KEY,
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL,
    key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fetch_count INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS object_store_key_nocase_unique
    ON object_store (key COLLATE NOCASE)`,
  `CREATE UNIQUE INDEX IF NOT EXISTS object_store_file_unique_id_unique
    ON object_store (file_unique_id)`,
  `CREATE TABLE IF NOT EXISTS quote_db (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_user_id INTEGER NOT NULL,
    saver_user_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    forwarded_message_id INTEGER
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS quote_db_chat_message_unique
    ON quote_db (chat_id, message_id)`,
  `CREATE TABLE IF NOT EXISTS quote_recent_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    quote_id INTEGER NOT NULL,
    shown_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quote_id) REFERENCES quote_db(id)
  )`,
  `CREATE INDEX IF NOT EXISTS quote_recent_history_chat_time_index
    ON quote_recent_history (chat_id, shown_time)`,
  `CREATE TABLE IF NOT EXISTS summon_groups (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_id INTEGER NOT NULL
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS summon_groups_chat_name_unique
    ON summon_groups (chat_id, group_name COLLATE NOCASE)`,
  `CREATE TABLE IF NOT EXISTS summon_group_members (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, user_id)
  )`,
  `CREATE TABLE IF NOT EXISTS habit (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    habit_name TEXT NOT NULL,
    weekly_goal INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_id INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS habit_members (
    habit_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (habit_id, user_id)
  )`,
  `CREATE TABLE IF NOT EXISTS habit_log (
    id INTEGER PRIMARY KEY,
    habit_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  )`,
  `CREATE TABLE IF NOT EXISTS highlights (
    id INTEGER PRIMARY KEY,
    string TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enabled INTEGER NOT NULL DEFAULT 1
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS highlights_chat_user_string_unique
    ON highlights (chat_id, user_id, string COLLATE NOCASE)`,
  `CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    target_time INTEGER NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claim_time INTEGER,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
  )`,
  `CREATE INDEX IF NOT EXISTS reminders_due_claim_index
    ON reminders (target_time, claim_time)`,
  `CREATE TABLE IF NOT EXISTS user_command_limits (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    \`limit\` INTEGER NOT NULL,
    current_usage INTEGER NOT NULL DEFAULT 0,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS user_command_limits_user_command_unique
    ON user_command_limits (user_id, command)`,
  `CREATE TABLE IF NOT EXISTS tldw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    summary TEXT,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  )`,
] as const;

export function initializeDatabase(database: Database) {
  return Effect.forEach(statements, (statement) => database.execute(statement), {
    concurrency: 1,
    discard: true,
  });
}
