import { createClient } from "@libsql/client";
import { expect, test } from "bun:test";
import { Effect } from "telly";

import { Database } from "../src/app/database.ts";
import { initializeDatabase } from "../src/app/schema.ts";
import { querySchema } from "../src/app/query-schema.ts";

test("database from all 33 Python migrations preserves rows during TypeScript initialization", async () => {
  const client = createClient({ intMode: "number", url: "file::memory:" });
  const database = new Database(client);
  const legacySchema = await Bun.file(new URL("fixtures/legacy-schema.sql", import.meta.url)).text();
  await client.executeMultiple(legacySchema);
  await Effect.runPromise(database.batch([
    {
      args: [7, "ayaan", "Ayaan"],
      sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)",
    },
    {
      args: [9, 42, -1007, 7, 8, null],
      sql: `INSERT INTO quote_db (
        id, message_id, chat_id, message_user_id, saver_user_id, forwarded_message_id
      ) VALUES (?, ?, ?, ?, ?, ?)`,
    },
    {
      args: [-1007, 1, 1, "openrouter/google/gemini-3-flash-preview"],
      sql: "INSERT INTO group_settings (chat_id, fts, auto_dl, search_model) VALUES (?, ?, ?, ?)",
    },
  ]));

  await Effect.runPromise(initializeDatabase(database));

  const user = await Effect.runPromise(database.one(
    "SELECT user_id, username, first_name FROM user_stats WHERE user_id = ?",
    [7],
  ));
  const quote = await Effect.runPromise(database.one(
    "SELECT forwarded_message_id FROM quote_db WHERE id = ?",
    [9],
  ));
  const setting = await Effect.runPromise(database.one(
    "SELECT fts, auto_dl, search_model, video_model FROM group_settings WHERE chat_id = ?",
    [-1007],
  ));
  const cronColumns = await Effect.runPromise(database.all("PRAGMA table_info(cron_tasks)"));
  const legacyTable = await Effect.runPromise(database.one(
    "SELECT name FROM sqlite_schema WHERE type = 'table' AND name = 'tv_shows'",
  ));
  database.close();

  expect(user).toMatchObject({ first_name: "Ayaan", user_id: 7, username: "ayaan" });
  expect(quote?.["forwarded_message_id"]).toBeNull();
  expect(setting).toMatchObject({
    auto_dl: 1,
    fts: 1,
    search_model: "openrouter/google/gemini-3-flash-preview",
    video_model: null,
  });
  expect(cronColumns.map((row) => row["name"])).toEqual(expect.arrayContaining([
    "next_run_time",
    "claim_time",
    "attempt_count",
  ]));
  expect(legacyTable?.["name"]).toBe("tv_shows");
});

test("query migration upgrades an existing database without replacing source or embedding rows", async () => {
  const client = createClient({ intMode: "number", url: "file::memory:" });
  const database = new Database(client);
  try {
    await client.executeMultiple(await Bun.file(new URL("fixtures/legacy-schema.sql", import.meta.url)).text());
    await client.execute("INSERT INTO user_stats (user_id, username) VALUES (7, 'Alice')");
    await client.execute("INSERT INTO chat_stats (chat_id, user_id, message_id, message_text) VALUES (-1007, 7, 20, 'history')");
    const tables = ["user_stats", "chat_stats", "chat_search_windows", "chat_search_utterances"];
    const before = await Promise.all(tables.map((table) => client.execute(`SELECT * FROM ${table}`)));
    for (const statement of querySchema) await Effect.runPromise(database.execute(statement));
    for (const statement of querySchema) await Effect.runPromise(database.execute(statement));
    const after = await Promise.all(tables.map((table) => client.execute(`SELECT * FROM ${table}`)));
    expect(after.map((result) => result.rows)).toEqual(before.map((result) => result.rows));
    expect((await client.execute("SELECT * FROM chat_search_progress")).rows).toEqual([]);
    const plan = await client.execute("EXPLAIN QUERY PLAN SELECT user_id FROM user_stats WHERE LOWER(username) = 'alice'");
    expect(plan.rows.some((row) => String(row["detail"]).includes("SEARCH user_stats USING INDEX"))).toBe(true);
  } finally {
    database.close();
  }
});
