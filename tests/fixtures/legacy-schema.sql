CREATE TABLE chat_aliases (
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            alias TEXT NOT NULL, confidence REAL NOT NULL,
            update_time DATETIME NOT NULL,
            PRIMARY KEY (chat_id, alias)
        );
CREATE TABLE chat_lore (
            chat_id INTEGER NOT NULL, topic TEXT NOT NULL,
            summary TEXT NOT NULL, receipts TEXT NOT NULL,
            source_end_message_id INTEGER NOT NULL,
            update_time DATETIME NOT NULL,
            PRIMARY KEY (chat_id, topic)
        );
CREATE TABLE chat_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            mentioning_user_id INTEGER NOT NULL,
            mentioned_user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        );
CREATE TABLE chat_personas (
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            sheet TEXT NOT NULL, receipts TEXT NOT NULL,
            source_end_message_id INTEGER NOT NULL,
            update_time DATETIME NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );
CREATE TABLE chat_search_utterances (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            start_message_id INTEGER NOT NULL,
            end_message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            message_count INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            embedding F32_BLOB(256) NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimension INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                chat_id,
                start_message_id,
                embedding_model,
                embedding_dimension
            )
        );
CREATE TABLE chat_search_windows (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            start_message_id INTEGER NOT NULL,
            end_message_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            message_count INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            embedding F32_BLOB(1024) NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimension INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                chat_id,
                start_message_id,
                end_message_id,
                embedding_model,
                embedding_dimension
            )
        );
CREATE TABLE chat_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            message_id INTEGER,
            message_text TEXT
        , reply_to_message_id INTEGER, reply_to_user_id INTEGER);
CREATE VIRTUAL TABLE chat_stats_fts USING fts5(
            message_text,
            chat_id UNINDEXED,
            content='chat_stats',
            content_rowid='id'
        );
CREATE TABLE command_blocklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            command TEXT NOT NULL,
            blocked_by INTEGER NOT NULL,
            blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, command)
        );
CREATE TABLE command_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command VARCHAR(255) NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        , chat_id INTEGER, message_id INTEGER, username TEXT, input_text TEXT, status TEXT NOT NULL DEFAULT 'completed', duration_ms INTEGER, error_type TEXT, error_message TEXT, error_traceback TEXT);
CREATE TABLE command_whitelist (
            command VARCHAR(255) NOT NULL,
            whitelist_type VARCHAR(255) NOT NULL DEFAULT 'USER',
            whitelist_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (command, whitelist_type, whitelist_id)
        );
CREATE TABLE cron_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cron_task_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            result_text TEXT,
            error_text TEXT,
            start_time DATETIME NOT NULL,
            finish_time DATETIME NOT NULL,
            FOREIGN KEY (cron_task_id) REFERENCES cron_tasks(id)
        );
CREATE TABLE cron_tasks (
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
        , next_run_time INTEGER, claim_time INTEGER, attempt_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE football_alert_deliveries (
            provider_id TEXT NOT NULL,
            kickoff_time INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            delivery_time INTEGER NOT NULL,
            PRIMARY KEY (provider_id, kickoff_time, chat_id, user_id)
        );
CREATE TABLE football_alert_members (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id)
        );
CREATE TABLE football_fixtures (
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
        );
CREATE TABLE "group_settings" (
            chat_id INTEGER PRIMARY KEY,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fts TINYINT NOT NULL DEFAULT 0,
            steam_offers TINYINT NOT NULL DEFAULT 0,
            ask_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast',
            edit_model TEXT DEFAULT 'openrouter/google/gemini-2.5-flash-image-preview',
            tr_model TEXT DEFAULT 'google/gemini-2.5-flash',
            tldr_model TEXT DEFAULT 'openrouter/x-ai/grok-4-fast'
        , ask_thinking TEXT DEFAULT 'none', auto_dl TINYINT NOT NULL DEFAULT 0, search_model TEXT DEFAULT 'openrouter/x-ai/grok-4.3', cron_model TEXT DEFAULT 'openrouter/x-ai/grok-4.3', song_model TEXT DEFAULT 'openrouter/x-ai/grok-4.3');
CREATE TABLE habit (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            habit_name VARCHAR(255) NOT NULL,
            weekly_goal INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creator_id INTEGER NOT NULL
        );
CREATE TABLE habit_log (
            id INTEGER PRIMARY KEY,
            habit_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habit(id)
        );
CREATE TABLE habit_members (
            habit_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habit(id),
            PRIMARY KEY (habit_id, user_id)
        );
CREATE TABLE highlights (
            id INTEGER PRIMARY KEY,
            string VARCHAR(255) NOT NULL,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            enabled INTEGER NOT NULL DEFAULT 1
        );
CREATE TABLE object_store (
            id INTEGER PRIMARY KEY,
            file_id VARCHAR(255) NOT NULL,
            file_unique_id VARCHAR(255) NOT NULL,
            key VARCHAR(255) NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            type VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fetch_count INTEGER NOT NULL DEFAULT 0
        );
CREATE TABLE quote_db (
            id INTEGER PRIMARY KEY,
            message_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_user_id INTEGER NOT NULL,
            saver_user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            forwarded_message_id INTEGER NULL
        );
CREATE TABLE quote_recent_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            quote_id INTEGER NOT NULL,
            shown_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quote_id) REFERENCES quote_db(id)
        );
CREATE TABLE reddit_subscriptions (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            subreddit_name VARCHAR(255) NOT NULL,
            receiver_id INTEGER NOT NULL,
            receiver_username VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE reminders (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title VARCHAR(255) NOT NULL,
            target_time INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        , claim_time INTEGER, attempt_count INTEGER NOT NULL DEFAULT 0, last_error TEXT);
CREATE TABLE search_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            question TEXT NOT NULL, answer TEXT NOT NULL, model TEXT NOT NULL,
            citation_message_ids TEXT NOT NULL,
            duration_ms INTEGER NOT NULL
        , lane TEXT NOT NULL DEFAULT 'fact');
CREATE TABLE steam_offers (
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
        , notified BOOLEAN DEFAULT FALSE);
CREATE TABLE "summon_group_members" (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (group_id, user_id)
        );
CREATE TABLE summon_groups (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            group_name VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creator_id INTEGER NOT NULL
        );
CREATE TABLE tldw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id VARCHAR(255) NOT NULL,
                user_id INTEGER NOT NULL,
                summary TEXT,
                create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE tv_notifications (
            id INTEGER PRIMARY KEY,
            user_id SIGNED INTEGER NOT NULL,
            show_id VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE tv_opt_in (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            chat_id VARCHAR(255) NOT NULL,
            username VARCHAR(255) NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE tv_shows (
            id INTEGER PRIMARY KEY,
            show_id VARCHAR(255) NOT NULL,
            show_name VARCHAR(255) NOT NULL,
            show_image VARCHAR(255) NOT NULL,
            next_episode_time INTEGER NULL,
            next_episode_name VARCHAR(255) NULL,
            sent INTEGER NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE user_command_limits (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            command VARCHAR(255) NOT NULL,
            `limit` INTEGER NOT NULL,
            current_usage INTEGER NOT NULL DEFAULT 0,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE user_stats (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            last_seen DATETIME,
            last_message_link TEXT
        , first_name TEXT);
CREATE TABLE video_history (
                subscription_id INTEGER,
                video_id TEXT,
                status TEXT,
                create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (subscription_id, video_id)
            );
CREATE TABLE weather_cache (
            user_id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE youtube_subscribers (
            id INTEGER PRIMARY KEY,
            subscription_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE youtube_subscriptions (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            channel_id VARCHAR(255) NOT NULL,
            latest_video_id VARCHAR(255) NOT NULL,
            creator_id INTEGER NOT NULL,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE INDEX chat_search_utterances_chat_idx
        ON chat_search_utterances (chat_id, embedding_model, embedding_dimension)
        ;
CREATE INDEX chat_search_utterances_member_idx
        ON chat_search_utterances (chat_id, user_id, end_message_id)
        ;
CREATE INDEX chat_search_utterances_range_idx
        ON chat_search_utterances (chat_id, end_message_id, start_message_id, user_id)
        ;
CREATE INDEX chat_search_windows_chat_range_idx
        ON chat_search_windows (chat_id, start_message_id, end_message_id)
        ;
CREATE INDEX chat_stats_chat_message_id_index
        ON chat_stats (chat_id, message_id)
    ;
CREATE UNIQUE INDEX chat_stats_chat_user_message_id_index
        ON chat_stats (chat_id, user_id, message_id)
    ;
CREATE INDEX command_stats_create_time_index
        ON command_stats (create_time)
        ;
CREATE INDEX command_stats_user_id_command_index
        ON command_stats (command, user_id)
    ;
CREATE INDEX cron_runs_task_id_desc_index
        ON cron_runs(cron_task_id, id DESC)
    ;
CREATE INDEX cron_tasks_enabled_index
        ON cron_tasks(enabled, chat_id, user_id)
    ;
CREATE INDEX football_fixtures_due_index
        ON football_fixtures (status, alert_time, kickoff_time)
    ;
CREATE INDEX highlight_words_word_index
        ON highlights (string)
    ;
CREATE UNIQUE INDEX highlights_chat_user_string_unique
        ON highlights (chat_id, user_id, string COLLATE NOCASE)
        ;
CREATE INDEX idx_chat_mentions_chat_count
        ON chat_mentions(chat_id)
        WHERE mentioning_user_id != mentioned_user_id;
CREATE INDEX idx_chat_mentions_chat_create
        ON chat_mentions(chat_id, create_time);
CREATE INDEX idx_chat_mentions_incoming
        ON chat_mentions(chat_id, mentioned_user_id, mentioning_user_id);
CREATE INDEX idx_chat_mentions_incoming_message
        ON chat_mentions (chat_id, mentioned_user_id, message_id)
        ;
CREATE INDEX idx_chat_mentions_network
        ON chat_mentions(chat_id, mentioning_user_id, mentioned_user_id);
CREATE UNIQUE INDEX object_store_file_unique_id_unique
        ON object_store (file_unique_id)
        ;
CREATE UNIQUE INDEX object_store_key_nocase_unique
        ON object_store (key COLLATE NOCASE)
        ;
CREATE UNIQUE INDEX quote_db_chat_message_unique
        ON quote_db (chat_id, message_id)
        ;
CREATE INDEX quote_recent_history_chat_time_index
        ON quote_recent_history (chat_id, shown_time)
        ;
CREATE INDEX reminders_due_claim_index
        ON reminders (target_time, claim_time)
        ;
CREATE INDEX search_events_chat_time_index ON search_events (chat_id, create_time);
CREATE UNIQUE INDEX summon_groups_chat_name_unique
        ON summon_groups (chat_id, group_name COLLATE NOCASE)
        ;
CREATE INDEX summon_groups_group_name_index
        ON summon_groups (group_name)
    ;
CREATE INDEX tv_opt_in_user_id_chat_id_index
        ON tv_opt_in (user_id, chat_id)
    ;
CREATE UNIQUE INDEX user_command_limits_user_command_unique
        ON user_command_limits (user_id, command)
        ;
CREATE TRIGGER chat_stats_ai AFTER INSERT ON chat_stats BEGIN
            INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
            VALUES (new.id, new.message_text, new.chat_id);
        END;
