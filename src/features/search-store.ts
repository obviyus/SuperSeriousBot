import { Database as Sqlite } from "bun:sqlite";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { Effect } from "telly";

import { rowNumber } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { excludedUserIds } from "./search-agent.ts";

// Each search-enabled chat gets a local read-only SQLite copy of its own
// history for the /search agent. It holds only that chat, without opted-out
// members, so the agent can run any query without reaching other chats.
// Sync pulls only rows newer than the last copied row id; chat_stats and
// chat_mentions are append-only, so this never misses an insert.

const schemaVersion = "1";
const batchSize = 5_000;

const localSchema = `
  PRAGMA journal_mode = WAL;
  CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    time TEXT NOT NULL,
    text TEXT,
    reply_to_message_id INTEGER
  );
  CREATE INDEX IF NOT EXISTS messages_user ON messages (user_id, message_id);
  CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text, content='messages', content_rowid='message_id', tokenize='unicode61 remove_diacritics 2'
  );
  CREATE TABLE IF NOT EXISTS members (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    aliases TEXT NOT NULL DEFAULT '[]',
    profile TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    first_message_time TEXT,
    last_message_time TEXT
  );
  CREATE TABLE IF NOT EXISTS interactions (
    user_id INTEGER NOT NULL,
    other_user_id INTEGER NOT NULL,
    mentions_or_replies INTEGER NOT NULL,
    PRIMARY KEY (user_id, other_user_id)
  );
`;

export function searchStorePath(stateDirectory: string, chatId: number): string {
  return join(stateDirectory, "search", `${chatId}.db`);
}

function openStore(path: string): Sqlite {
  mkdirSync(join(path, ".."), { recursive: true });
  const store = new Sqlite(path, { create: true });
  store.exec(localSchema);
  return store;
}

function meta(store: Sqlite, key: string): string | undefined {
  const row = store.query("SELECT value FROM meta WHERE key = ?").get(key) as { value: string } | null;
  return row?.value;
}

function setMeta(store: Sqlite, key: string, value: string | number) {
  store.query("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value")
    .run(key, String(value));
}

const syncChat = Effect.fn("syncSearchStore")(function* (
  dependencies: AppDependencies,
  chatId: number,
  excluded: ReadonlySet<number>,
) {
  const path = searchStorePath(dependencies.config.stateDirectory, chatId);
  let store = openStore(path);
  const fingerprint = JSON.stringify({ excluded: [...excluded].sort(), schemaVersion });
  if (meta(store, "fingerprint") !== fingerprint) {
    // A new opt-out or schema rebuilds the copy from scratch.
    store.close();
    for (const suffix of ["", "-wal", "-shm"]) yield* Effect.promise(() => Bun.file(`${path}${suffix}`).delete().catch(() => {}));
    store = openStore(path);
    setMeta(store, "fingerprint", fingerprint);
  }
  try {
    const keep = (userId: number) => !excluded.has(userId);
    const insertMessage = store.prepare(
      `INSERT OR IGNORE INTO messages (message_id, user_id, time, text, reply_to_message_id)
       VALUES (?, ?, ?, ?, ?)`,
    );
    const indexText = store.prepare("INSERT INTO messages_fts (rowid, text) VALUES (?, ?)");
    const countMember = store.prepare(
      `INSERT INTO members (user_id, message_count, first_message_time, last_message_time) VALUES (?, 1, ?, ?)
       ON CONFLICT(user_id) DO UPDATE SET message_count = message_count + 1,
         first_message_time = MIN(COALESCE(first_message_time, excluded.first_message_time), excluded.first_message_time),
         last_message_time = MAX(COALESCE(last_message_time, excluded.last_message_time), excluded.last_message_time)`,
    );
    let lastMessage = Number(meta(store, "chat_stats_id") ?? 0);
    while (true) {
      const rows = yield* dependencies.database.all(
        `SELECT id, user_id, message_id, message_text, create_time, reply_to_message_id
         FROM chat_stats WHERE chat_id = ? AND id > ? ORDER BY id LIMIT ?`,
        [chatId, lastMessage, batchSize],
      );
      if (rows.length === 0) break;
      store.transaction(() => {
        for (const row of rows) {
          // Rows from before 2024 have no message ID or text, and channel posts
          // have a text user ID; neither can be searched or cited.
          const userId = row["user_id"];
          const messageId = row["message_id"];
          if (typeof userId !== "number" || !keep(userId) || messageId === null) continue;
          const text = typeof row["message_text"] === "string" ? row["message_text"] : null;
          const time = String(row["create_time"]);
          const replyTo = row["reply_to_message_id"];
          const inserted = insertMessage.run(Number(messageId), userId, time, text, replyTo === null ? null : Number(replyTo));
          if (inserted.changes === 0) continue;
          if (text !== null && text.length > 0) indexText.run(Number(messageId), text);
          countMember.run(userId, time, time);
        }
        lastMessage = rowNumber(rows.at(-1)!, "id");
        setMeta(store, "chat_stats_id", lastMessage);
      })();
      if (rows.length < batchSize) break;
    }

    const addInteraction = store.prepare(
      `INSERT INTO interactions (user_id, other_user_id, mentions_or_replies) VALUES (?, ?, 1)
       ON CONFLICT(user_id, other_user_id) DO UPDATE SET mentions_or_replies = mentions_or_replies + 1`,
    );
    let lastMention = Number(meta(store, "chat_mentions_id") ?? 0);
    while (true) {
      const rows = yield* dependencies.database.all(
        `SELECT id, mentioning_user_id, mentioned_user_id FROM chat_mentions
         WHERE chat_id = ? AND id > ? ORDER BY id LIMIT ?`,
        [chatId, lastMention, batchSize],
      );
      if (rows.length === 0) break;
      store.transaction(() => {
        for (const row of rows) {
          const from = row["mentioning_user_id"];
          const to = row["mentioned_user_id"];
          if (typeof from !== "number" || typeof to !== "number") continue;
          if (from !== to && keep(from) && keep(to)) addInteraction.run(from, to);
        }
        lastMention = rowNumber(rows.at(-1)!, "id");
        setMeta(store, "chat_mentions_id", lastMention);
      })();
      if (rows.length < batchSize) break;
    }

    // Names, aliases and profiles are small, so refresh them every sync.
    const ids = (store.query("SELECT user_id FROM members").all() as Array<{ user_id: number }>).map((row) => row.user_id);
    const names = ids.length === 0 ? [] : yield* dependencies.database.all(
      `SELECT user_id, username, first_name FROM user_stats WHERE user_id IN (${ids.map(() => "?").join(",")})`,
      ids,
    );
    const aliases = yield* dependencies.database.all(
      "SELECT user_id, alias FROM chat_aliases WHERE chat_id = ? AND confidence >= 0.5",
      [chatId],
    );
    const profiles = yield* dependencies.database.all(
      "SELECT user_id, sheet FROM chat_personas WHERE chat_id = ?",
      [chatId],
    );
    store.transaction(() => {
      const update = store.prepare(
        "UPDATE members SET username = ?, first_name = ?, aliases = ?, profile = ? WHERE user_id = ?",
      );
      for (const row of names) {
        const userId = rowNumber(row, "user_id");
        const text = (value: unknown) => typeof value === "string" ? value : null;
        update.run(
          text(row["username"]),
          text(row["first_name"]),
          JSON.stringify(aliases.filter((alias) => rowNumber(alias, "user_id") === userId).map((alias) => alias["alias"])),
          text(profiles.find((profile) => rowNumber(profile, "user_id") === userId)?.["sheet"]),
          userId,
        );
      }
      setMeta(store, "synced_at", new Date().toISOString());
    })();
  } finally {
    store.close();
  }
});

export const syncSearchStores = Effect.fn("syncSearchStores")(function* (
  dependencies: AppDependencies,
  chatIds?: ReadonlyArray<number>,
) {
  const excluded = yield* excludedUserIds(dependencies);
  const ids = chatIds ?? (yield* dependencies.database.all(
    "SELECT chat_id FROM group_settings WHERE fts = 1 ORDER BY chat_id",
  )).map((row) => rowNumber(row, "chat_id"));
  for (const chatId of ids) {
    yield* syncChat(dependencies, chatId, excluded).pipe(
      Effect.catchCause((cause) => Effect.logError("Search store sync failed").pipe(
        Effect.annotateLogs({ cause: String(cause), chatId }),
      )),
    );
  }
});
