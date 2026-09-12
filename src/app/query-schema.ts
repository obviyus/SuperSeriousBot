import { Effect } from "telly";

import type { Database } from "./database.ts";

export const querySchema = [
  `CREATE INDEX IF NOT EXISTS user_stats_username_index ON user_stats (LOWER(username))`,
  `CREATE INDEX IF NOT EXISTS chat_stats_member_latest_index ON chat_stats (chat_id, user_id, id)`,
  `CREATE INDEX IF NOT EXISTS chat_search_windows_latest_index ON chat_search_windows (chat_id, end_message_id)`,
  `CREATE INDEX IF NOT EXISTS chat_search_utterances_progress_index
    ON chat_search_utterances (chat_id, embedding_model, embedding_dimension, start_message_id, end_message_id)`,
  `CREATE TABLE IF NOT EXISTS chat_search_progress (
    chat_id INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    window_dimension INTEGER NOT NULL,
    utterance_dimension INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    indexed_revision INTEGER NOT NULL DEFAULT -1,
    generation INTEGER NOT NULL DEFAULT 0,
    rebuild INTEGER NOT NULL DEFAULT 1,
    end_message_id INTEGER,
    window_tail TEXT NOT NULL DEFAULT '[]',
    utterance_tail TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (chat_id, embedding_model, window_dimension, utterance_dimension)
  )`,
  `CREATE TRIGGER IF NOT EXISTS chat_search_source_insert AFTER INSERT ON chat_stats BEGIN
    UPDATE chat_search_progress SET revision = revision + 1,
      generation = generation + CASE WHEN NEW.message_id <= (
        SELECT message_id FROM chat_stats
        WHERE chat_id = NEW.chat_id AND id != NEW.id AND message_id IS NOT NULL
        ORDER BY message_id DESC LIMIT 1
      ) THEN 1 ELSE 0 END,
      rebuild = CASE WHEN NEW.message_id <= (
        SELECT message_id FROM chat_stats
        WHERE chat_id = NEW.chat_id AND id != NEW.id AND message_id IS NOT NULL
        ORDER BY message_id DESC LIMIT 1
      ) THEN 1 ELSE rebuild END
    WHERE chat_id = NEW.chat_id;
  END`,
  `CREATE TRIGGER IF NOT EXISTS chat_search_source_update
    AFTER UPDATE OF chat_id, user_id, message_id, message_text, create_time ON chat_stats
    WHEN OLD.chat_id IS NOT NEW.chat_id OR OLD.user_id IS NOT NEW.user_id
      OR OLD.message_id IS NOT NEW.message_id OR OLD.message_text IS NOT NEW.message_text
      OR OLD.create_time IS NOT NEW.create_time
    BEGIN
      UPDATE chat_search_progress SET revision = revision + 1, generation = generation + 1, rebuild = 1
      WHERE chat_id IN (OLD.chat_id, NEW.chat_id);
    END`,
  `CREATE TRIGGER IF NOT EXISTS chat_search_source_delete AFTER DELETE ON chat_stats BEGIN
    UPDATE chat_search_progress SET revision = revision + 1, generation = generation + 1, rebuild = 1 WHERE chat_id = OLD.chat_id;
  END`,
  `CREATE TRIGGER IF NOT EXISTS chat_search_author_insert AFTER INSERT ON user_stats BEGIN
    UPDATE chat_search_progress SET revision = revision + 1, generation = generation + 1, rebuild = 1
    WHERE EXISTS (SELECT 1 FROM chat_stats WHERE chat_id = chat_search_progress.chat_id AND user_id = NEW.user_id);
  END`,
  `CREATE TRIGGER IF NOT EXISTS chat_search_author_update AFTER UPDATE OF username ON user_stats
    WHEN OLD.username IS NOT NEW.username
    BEGIN
      UPDATE chat_search_progress SET revision = revision + 1, generation = generation + 1, rebuild = 1
      WHERE EXISTS (SELECT 1 FROM chat_stats WHERE chat_id = chat_search_progress.chat_id AND user_id = NEW.user_id);
    END`,
  `CREATE TRIGGER IF NOT EXISTS chat_search_author_delete AFTER DELETE ON user_stats BEGIN
    UPDATE chat_search_progress SET revision = revision + 1, generation = generation + 1, rebuild = 1
    WHERE EXISTS (SELECT 1 FROM chat_stats WHERE chat_id = chat_search_progress.chat_id AND user_id = OLD.user_id);
  END`,
] as const;

export const migrateQuerySchema = Effect.fn("migrateQuerySchema")(function* (database: Database) {
  const columns = yield* database.all("PRAGMA table_info(chat_search_progress)");
  yield* database.batch([
    ...(columns.length > 0 && !columns.some((column) => column["name"] === "generation")
      ? [{ sql: "ALTER TABLE chat_search_progress ADD COLUMN generation INTEGER NOT NULL DEFAULT 0" }]
      : []),
    ...["source_insert", "source_update", "source_delete", "author_insert", "author_update", "author_delete"]
      .map((name) => ({ sql: `DROP TRIGGER IF EXISTS chat_search_${name}` })),
    ...querySchema.map((sql) => ({ sql })),
  ]);
});
