import { expect, spyOn, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import { type Database } from "../src/app/database.ts";
import { migrateQuerySchema, querySchema } from "../src/app/query-schema.ts";
import { initializeDatabase } from "../src/app/schema.ts";
import { createSuperSeriousBot } from "../src/bot.ts";
import { commandUpdate, fixture, openRouterEmbeddings, openRouterText, testConfig } from "./harness.ts";

function observeReads(database: Database) {
  const execute = database.execute.bind(database);
  const reads: Array<{ sql: string; rows: number; plan: ReadonlyArray<string> }> = [];
  const spy = spyOn(database, "execute").mockImplementation((sql, args = []) =>
    execute(sql, args).pipe(Effect.tap((result) => {
      if (!sql.trimStart().startsWith("SELECT")) return Effect.void;
      return execute(`EXPLAIN QUERY PLAN ${sql}`, args).pipe(Effect.map((plan) => {
        reads.push({ sql, rows: result.rows.length, plan: plan.rows.map((row) => String(row["detail"])) });
      }));
    })));
  return { reads, stop: () => spy.mockRestore() };
}

function insertMessages(database: Database, start: number, count: number) {
  return Effect.runPromise(database.batch(Array.from({ length: count }, (_, index) => ({
    args: [-1007, 2, start + index, new Date(Date.UTC(2026, 0, 1, 0, start + index)).toISOString(), `message ${start + index}`],
    sql: "INSERT INTO chat_stats (chat_id, user_id, message_id, create_time, message_text) VALUES (?, ?, ?, ?, ?)",
  }))));
}

test("indexing reads only new messages and unfinished tails across worker restarts", async () => {
  let embeddings = 0;
  const { app, bot, database, dependencies } = await fixture(async (_input, init) => {
    embeddings += 1;
    return openRouterEmbeddings(String(init?.body));
  }, [], testConfig({ openrouterApiKey: "test" }));
  await insertMessages(database, 1, 2_400);
  try {
    await app.run(bot.workers.search.index([-1007]));
    const initialCalls = embeddings;
    const observed = observeReads(database);
    await app.run(createSuperSeriousBot(dependencies).workers.search.index([-1007]));
    const unchangedRows = observed.reads.reduce((sum, read) => sum + read.rows, 0);
    expect(embeddings).toBe(initialCalls);
    expect(unchangedRows).toBeLessThan(10);
    observed.reads.length = 0;
    await insertMessages(database, 2_401, 10);
    await app.run(createSuperSeriousBot(dependencies).workers.search.index([-1007]));
    const appendRows = observed.reads.reduce((sum, read) => sum + read.rows, 0);
    expect(appendRows).toBeLessThan(100);
    expect(observed.reads.filter((read) => read.sql.includes("FROM chat_stats messages"))
      .flatMap((read) => read.plan).some((detail) => detail.includes("message_id>?"))).toBe(true);
    console.log({ unchangedRows, appendRows });
    observed.stop();
  } finally {
    await app.close();
    database.close();
  }
});

test("seen resolves usernames before looking up each user's latest inserted message", async () => {
  const { app, bot, database, fake } = await fixture(async () => new Response("{}"), [
    FakeBotApiReply.ok(true), FakeBotApiReply.ok(true),
  ]);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username) VALUES (2, 'Alice'), (3, 'aLiCe')" },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id, create_time) VALUES (-1007, 2, 9000, '2026-01-01'), (-1007, 3, 8000, '2026-01-02'), (-1008, 2, 9999, '2026-01-03'), (-1007, 2, 7, '2026-01-04')" },
  ]));
  const observed = observeReads(database);
  try {
    await app.run(bot.handler(commandUpdate("/seen @ALICE", 10001)));
    expect(JSON.stringify(fake.requests)).toContain("https://t.me/c/7/7");
    const lookup = observed.reads.find((read) => read.sql.includes("LOWER(us.username)"));
    expect(lookup).toBeDefined();
    expect(lookup?.plan.some((detail) => detail.includes("SEARCH us USING INDEX"))).toBe(true);
    expect(lookup?.plan.some((detail) => detail.includes("chat_id=? AND user_id=?"))).toBe(true);
    expect(lookup?.plan.some((detail) => detail.startsWith("SEARCH cs") && detail.endsWith("(chat_id=?)"))).toBe(false);
  } finally {
    observed.stop();
    await app.close();
    database.close();
  }
});

test("passive username resolution uses an index", async () => {
  const { app, bot, database } = await fixture(async () => openRouterText('{"items":[]}'), [], testConfig({ openrouterApiKey: "test" }));
  await Effect.runPromise(database.execute("INSERT INTO user_stats (user_id, username) VALUES (2, 'Alice')"));
  const observed = observeReads(database);
  try {
    const update = commandUpdate("@ALICE hi", 10002);
    if (update.message === undefined) throw new Error("Expected message");
    await app.run(bot.handler({ ...update, message: { ...update.message, entities: [{ type: "mention", offset: 0, length: 6 }] } }));
    const username = observed.reads.find((read) => read.sql.includes("LOWER(username)"));
    expect(username?.plan.some((detail) => detail.includes("SEARCH user_stats USING INDEX"))).toBe(true);
  } finally {
    observed.stop();
    await app.close();
    database.close();
  }
});

test("recent memory windows use an ordered index", async () => {
  const { app, bot, database } = await fixture(async () => openRouterText('{"items":[]}'), [], testConfig({ openrouterApiKey: "test" }));
  const observed = observeReads(database);
  try {
    await app.run(bot.workers.search.memory([-1007]));
    const recent = observed.reads.find((read) => read.sql.includes("FROM chat_search_windows"));
    expect(recent).toBeDefined();
    expect(recent?.plan.some((detail) => detail.includes("TEMP B-TREE"))).toBe(false);
  } finally {
    observed.stop();
    await app.close();
    database.close();
  }
});

async function searchRows(database: Database) {
  return {
    windows: await Effect.runPromise(database.all("SELECT start_message_id, end_message_id, message_text FROM chat_search_windows ORDER BY start_message_id, end_message_id")),
    utterances: await Effect.runPromise(database.all("SELECT start_message_id, end_message_id, message_text FROM chat_search_utterances ORDER BY start_message_id")),
  };
}

test("an older worker cannot overwrite a newer completed index", async () => {
  const entered = Promise.withResolvers<void>();
  const resume = Promise.withResolvers<void>();
  let block = true;
  const { app, bot, database, dependencies } = await fixture(async (_input, init) => {
    if (block) {
      block = false;
      entered.resolve();
      await resume.promise;
    }
    return openRouterEmbeddings(String(init?.body));
  }, [], testConfig({ openrouterApiKey: "test" }));
  await insertMessages(database, 1, 30);
  const older = app.run(bot.workers.search.index([-1007]));
  try {
    await entered.promise;
    await insertMessages(database, 31, 10);
    await app.run(createSuperSeriousBot(dependencies).workers.search.index([-1007]));
    const completed = await searchRows(database);
    resume.resolve();
    await older;
    expect(await searchRows(database)).toEqual(completed);
  } finally {
    resume.resolve();
    await older;
    await app.close();
    database.close();
  }
});

test("incremental indexing retains full-history behavior through imports, edits, deletes, and author changes", async () => {
  const send = async (_input: Parameters<typeof fetch>[0], init?: RequestInit) => openRouterEmbeddings(String(init?.body));
  const incremental = await fixture(send, [], testConfig({ openrouterApiKey: "test" }));
  const full = await fixture(send, [], testConfig({ openrouterApiKey: "test" }));
  const both = [incremental, full];
  const compare = async () => {
    await Effect.runPromise(full.database.execute("DELETE FROM chat_search_progress"));
    for (const setup of both) await setup.app.run(setup.bot.workers.search.index([-1007]));
    expect(await searchRows(incremental.database)).toEqual(await searchRows(full.database));
  };
  try {
    await compare();
    for (const setup of both) await insertMessages(setup.database, 10, 29);
    await compare();
    for (const count of [1, 2, 8, 12, 24, 65]) {
      const row = await Effect.runPromise(full.database.one("SELECT MAX(message_id) AS last FROM chat_stats"));
      for (const setup of both) await insertMessages(setup.database, Number(row?.["last"]) + 1, count);
      await compare();
    }
    for (const setup of both) await insertMessages(setup.database, 1, 9);
    await compare();
    for (const sql of [
      "UPDATE chat_stats SET message_text = 'edited', create_time = '2026-01-01T10:00:00Z' WHERE message_id = 3",
      "UPDATE chat_stats SET user_id = 3 WHERE message_id IN (25, 26, 27)",
      "DELETE FROM chat_stats WHERE message_id IN (2, 5, 28, 33)",
      "INSERT INTO user_stats (user_id, username) VALUES (2, 'Alice')",
      "UPDATE user_stats SET username = 'Bob' WHERE user_id = 2",
      "DELETE FROM user_stats WHERE user_id = 2",
    ]) {
      for (const setup of both) await Effect.runPromise(setup.database.execute(sql));
      await compare();
    }
    for (const setup of both) await insertMessages(setup.database, 200, 40);
    await compare();
    for (const setup of both) await Effect.runPromise(setup.database.execute("DELETE FROM chat_stats"));
    await compare();
    for (const setup of both) await insertMessages(setup.database, 300, 9);
    await compare();
  } finally {
    for (const setup of both) {
      await setup.app.close();
      setup.database.close();
    }
  }
});

test.each(["append", "older import"])("a %s during embedding remains pending for the next worker", async (change) => {
  const entered = Promise.withResolvers<void>();
  const resume = Promise.withResolvers<void>();
  let block = false;
  const { app, bot, database } = await fixture(async (_input, init) => {
    if (block) {
      block = false;
      entered.resolve();
      await resume.promise;
    }
    return openRouterEmbeddings(String(init?.body));
  }, [], testConfig({ openrouterApiKey: "test" }));
  try {
    await insertMessages(database, 10, 30);
    await app.run(bot.workers.search.index([-1007]));
    await insertMessages(database, 40, 10);
    block = true;
    const indexing = app.run(bot.workers.search.index([-1007]));
    await entered.promise;
    await insertMessages(database, change === "append" ? 50 : 1, 9);
    resume.resolve();
    await indexing;
    const pending = await Effect.runPromise(database.one("SELECT revision, indexed_revision FROM chat_search_progress"));
    expect(pending?.["revision"]).not.toBe(pending?.["indexed_revision"]);
    await app.run(bot.workers.search.index([-1007]));
    const indexed = await Effect.runPromise(database.one("SELECT revision, indexed_revision FROM chat_search_progress"));
    expect(indexed?.["revision"]).toBe(indexed?.["indexed_revision"]);
    const rows = await searchRows(database);
    expect(rows.windows.some((row) => String(row["message_text"]).includes(change === "append" ? "message 58" : "message 1\n"))).toBe(true);
  } finally {
    resume.resolve();
    await app.close();
    database.close();
  }
});

test("progress adds one write per tracked source insert and ignores unchanged usernames", async () => {
  const { app, bot, database } = await fixture(async (_input, init) => openRouterEmbeddings(String(init?.body)), [], testConfig({ openrouterApiKey: "test" }));
  const control = await fixture(async (_input, init) => openRouterEmbeddings(String(init?.body)), [], testConfig({ openrouterApiKey: "test" }));
  try {
    await Effect.runPromise(database.execute("INSERT INTO user_stats (user_id, username) VALUES (2, 'Alice')"));
    await insertMessages(database, 1, 30);
    await app.run(bot.workers.search.index([-1007]));
    await Effect.runPromise(control.database.execute("INSERT INTO user_stats (user_id, username) VALUES (2, 'Alice')"));
    await insertMessages(control.database, 1, 30);
    await control.app.run(control.bot.workers.search.index([-1007]));
    await Effect.runPromise(control.database.execute("DELETE FROM chat_search_progress"));
    const total = async () => Number((await Effect.runPromise(database.one("SELECT total_changes() AS count")))?.["count"]);
    const controlTotal = async () => Number((await Effect.runPromise(control.database.one("SELECT total_changes() AS count")))?.["count"]);
    const idleBefore = await total();
    await app.run(bot.workers.search.index([-1007]));
    expect(await total() - idleBefore).toBe(0);
    const before = await total();
    await insertMessages(database, 31, 1);
    const withProgress = await total() - before;
    const revision = await Effect.runPromise(database.one("SELECT revision FROM chat_search_progress"));
    await Effect.runPromise(database.execute("UPDATE user_stats SET username = 'Alice', last_seen = '2026-09-12' WHERE user_id = 2"));
    expect(await Effect.runPromise(database.one("SELECT revision FROM chat_search_progress"))).toEqual(revision);
    await Effect.runPromise(database.execute("UPDATE user_stats SET username = 'Renamed' WHERE user_id = 2"));
    const renamed = await Effect.runPromise(database.one("SELECT revision, rebuild FROM chat_search_progress"));
    expect(renamed?.["revision"]).toBe(Number(revision?.["revision"]) + 1);
    expect(renamed?.["rebuild"]).toBe(1);
    const baselineBefore = await controlTotal();
    await insertMessages(control.database, 31, 1);
    const withoutProgress = await controlTotal() - baselineBefore;
    expect(withProgress - withoutProgress).toBe(1);
    console.log({ insertWritesWithProgress: withProgress, insertWritesWithoutProgress: withoutProgress });
  } finally {
    await app.close();
    database.close();
    await control.app.close();
    control.database.close();
  }
});

test("a failed embedding pass does not advance progress and resumes through a fresh worker", async () => {
  let fail = true;
  const { app, bot, database, dependencies } = await fixture(async (_input, init) => {
    const body = String(init?.body);
    if (fail && JSON.parse(body).dimensions === 256) {
      fail = false;
      return new Response('{"error":{"message":"synthetic embedding failure"}}', { status: 400 });
    }
    return openRouterEmbeddings(body);
  }, [], testConfig({ openrouterApiKey: "test" }));
  try {
    await insertMessages(database, 1, 30);
    await expect(app.run(bot.workers.search.index([-1007]))).rejects.toBeDefined();
    const failed = await Effect.runPromise(database.one("SELECT indexed_revision FROM chat_search_progress"));
    expect(failed?.["indexed_revision"]).toBe(-1);
    await app.run(createSuperSeriousBot(dependencies).workers.search.index([-1007]));
    const complete = await Effect.runPromise(database.one("SELECT revision, indexed_revision FROM chat_search_progress"));
    expect(complete?.["revision"]).toBe(complete?.["indexed_revision"]);
    expect((await searchRows(database)).utterances.at(-1)?.["end_message_id"]).toBe(30);
  } finally {
    await app.close();
    database.close();
  }
});

test("additive migration preserves existing embedding configurations and checkpoints", async () => {
  const { app, bot, database } = await fixture(async (_input, init) => openRouterEmbeddings(String(init?.body)), [], testConfig({ openrouterApiKey: "test" }));
  try {
    await insertMessages(database, 1, 29);
    await app.run(bot.workers.search.index([-1007]));
    await Effect.runPromise(database.execute("UPDATE chat_search_windows SET embedding_model = 'previous-model'"));
    await Effect.runPromise(database.execute("UPDATE chat_search_utterances SET embedding_model = 'previous-model'"));
    const legacy = await searchRows(database);
    await Effect.runPromise(database.execute("DELETE FROM chat_search_progress"));
    for (const sql of querySchema) await Effect.runPromise(database.execute(sql));
    expect(await searchRows(database)).toEqual(legacy);
    await app.run(bot.workers.search.index([-1007]));
    const current = await Effect.runPromise(database.all("SELECT embedding_model, COUNT(*) AS count FROM chat_search_windows GROUP BY embedding_model"));
    expect(current.map((row) => row["count"])).toEqual([4, 4]);
    const progress = await Effect.runPromise(database.all("SELECT * FROM chat_search_progress"));
    for (const sql of querySchema) await Effect.runPromise(database.execute(sql));
    expect(await Effect.runPromise(database.all("SELECT * FROM chat_search_progress"))).toEqual(progress);
  } finally {
    await app.close();
    database.close();
  }
});

test.each([
  { warm: false, dimension: 1_024 },
  { warm: true, dimension: 1_024 },
  { warm: false, dimension: 256 },
  { warm: true, dimension: 256 },
])("indexing saves each captured prefix under sustained arrivals: %j", async ({ warm, dimension }) => {
  let armed = false;
  let maximum = 2_400;
  let calls = 0;
  let append: (count: number) => Promise<unknown>;
  const { app, bot, database } = await fixture(async (_input, init) => {
    calls += 1;
    const body = String(init?.body);
    if (armed && JSON.parse(body).dimensions === dimension) {
      armed = false;
      await append(1);
    }
    return openRouterEmbeddings(body);
  }, [], testConfig({ openrouterApiKey: "test" }));
  append = async (count) => {
    const result = await insertMessages(database, maximum + 1, count);
    maximum += count;
    return result;
  };
  const rounds: Array<{ sourceEnd: number; indexedEnd: unknown; windowsEnd: unknown; utterancesEnd: unknown; sourceRows: number; calls: number }> = [];
  try {
    await insertMessages(database, 1, maximum);
    if (warm) await app.run(bot.workers.search.index([-1007]));
    const observed = observeReads(database);
    for (let round = 0; round < 6; round++) {
      if (warm) await append(10);
      const sourceEnd = maximum;
      const previousCalls = calls;
      observed.reads.length = 0;
      armed = true;
      await app.run(bot.workers.search.index([-1007]));
      expect(armed).toBe(false);
      const progress = await Effect.runPromise(database.one("SELECT end_message_id FROM chat_search_progress"));
      const windows = await Effect.runPromise(database.one("SELECT MAX(end_message_id) AS last FROM chat_search_windows"));
      const utterances = await Effect.runPromise(database.one("SELECT MAX(end_message_id) AS last FROM chat_search_utterances"));
      rounds.push({ sourceEnd, indexedEnd: progress?.["end_message_id"], windowsEnd: windows?.["last"], utterancesEnd: utterances?.["last"],
        sourceRows: observed.reads.filter((read) => read.sql.includes("FROM chat_stats messages")).reduce((sum, read) => sum + read.rows, 0), calls: calls - previousCalls });
    }
    observed.stop();
    console.log({ warm, dimension, rounds });
    expect(rounds.map((round) => round.indexedEnd)).toEqual(rounds.map((round) => round.sourceEnd));
    expect(rounds.map((round) => round.windowsEnd)).toEqual(rounds.map((round) => round.sourceEnd));
    expect(rounds.map((round) => round.utterancesEnd)).toEqual(rounds.map((round) => round.sourceEnd));
    expect(rounds.slice(1).every((round) => round.sourceRows <= 11)).toBe(true);
  } finally {
    await app.close();
    database.close();
  }
});

test.each(["backfill", "edit", "delete", "rename"])("a %s inside the captured suffix invalidates it before publication", async (change) => {
  let armed = false;
  let calls = 0;
  const { app, bot, database } = await fixture(async (_input, init) => {
    calls += 1;
    if (armed) {
      armed = false;
      if (change === "backfill") await insertMessages(database, 2_450, 1);
      else await Effect.runPromise(database.execute(change === "edit"
        ? "UPDATE chat_stats SET message_text = 'edited suffix' WHERE message_id = 2460"
        : change === "delete" ? "DELETE FROM chat_stats WHERE message_id = 2460"
        : "UPDATE user_stats SET username = 'renamed' WHERE user_id = 2"));
    }
    return openRouterEmbeddings(String(init?.body));
  }, [], testConfig({ openrouterApiKey: "test" }));
  try {
    await Effect.runPromise(database.execute("INSERT INTO user_stats (user_id, username) VALUES (2, 'original')"));
    await insertMessages(database, 1, 2_400);
    await app.run(bot.workers.search.index([-1007]));
    await insertMessages(database, 2_401, 49);
    await insertMessages(database, 2_451, 50);
    calls = 0;
    armed = true;
    await app.run(bot.workers.search.index([-1007]));
    expect(calls).toBe(1);
    const interrupted = await Effect.runPromise(database.one("SELECT revision, indexed_revision, end_message_id FROM chat_search_progress"));
    expect(interrupted?.["end_message_id"]).toBe(2_400);
    expect(interrupted?.["revision"]).not.toBe(interrupted?.["indexed_revision"]);
    await app.run(bot.workers.search.index([-1007]));
    const complete = await Effect.runPromise(database.one("SELECT revision, indexed_revision, end_message_id FROM chat_search_progress"));
    expect(complete?.["end_message_id"]).toBe(2_500);
    expect(complete?.["revision"]).toBe(complete?.["indexed_revision"]);
    const rows = await searchRows(database);
    if (change === "backfill") expect(rows.windows.some((row) => String(row["message_text"]).includes("message 2450"))).toBe(true);
    if (change === "edit") expect(rows.windows.some((row) => String(row["message_text"]).includes("edited suffix"))).toBe(true);
  } finally {
    await app.close();
    database.close();
  }
});

test("excluded command and null-text appends do not stop a captured prefix", async () => {
  let armed = false;
  const { app, bot, database } = await fixture(async (_input, init) => {
    if (armed) {
      armed = false;
      await Effect.runPromise(database.execute("INSERT INTO chat_stats (chat_id, user_id, message_id, message_text) VALUES (-1007, 2, 41, '/command'), (-1007, 2, 42, NULL)"));
    }
    return openRouterEmbeddings(String(init?.body));
  }, [], testConfig({ openrouterApiKey: "test" }));
  try {
    await insertMessages(database, 1, 30);
    await app.run(bot.workers.search.index([-1007]));
    await insertMessages(database, 31, 10);
    armed = true;
    await app.run(bot.workers.search.index([-1007]));
    const prefix = await Effect.runPromise(database.one("SELECT end_message_id FROM chat_search_progress"));
    expect(prefix?.["end_message_id"]).toBe(40);
    await app.run(bot.workers.search.index([-1007]));
    const complete = await Effect.runPromise(database.one("SELECT revision, indexed_revision, end_message_id FROM chat_search_progress"));
    expect(complete?.["end_message_id"]).toBe(42);
    expect(complete?.["revision"]).toBe(complete?.["indexed_revision"]);
    expect((await searchRows(database)).utterances.at(-1)?.["end_message_id"]).toBe(40);
  } finally {
    await app.close();
    database.close();
  }
});

test("generation migration preserves the old worker's append signal and requires no startup cutover", async () => {
  const { app, bot, database } = await fixture(async (_input, init) => openRouterEmbeddings(String(init?.body)), [], testConfig({ openrouterApiKey: "test" }));
  try {
    await insertMessages(database, 1, 30);
    await app.run(bot.workers.search.index([-1007]));
    await Effect.runPromise(database.batch([
      ...["source_insert", "source_update", "source_delete", "author_insert", "author_update", "author_delete"]
        .map((name) => ({ sql: `DROP TRIGGER chat_search_${name}` })),
      { sql: "ALTER TABLE chat_search_progress DROP COLUMN generation" },
      { sql: `CREATE TRIGGER chat_search_source_insert AFTER INSERT ON chat_stats BEGIN
          UPDATE chat_search_progress SET revision = revision + 1,
            rebuild = CASE WHEN NEW.message_id <= end_message_id THEN 1 ELSE rebuild END
          WHERE chat_id = NEW.chat_id;
        END` },
    ]));
    const before = await searchRows(database);
    await Effect.runPromise(migrateQuerySchema(database));
    await Effect.runPromise(migrateQuerySchema(database));
    expect(await searchRows(database)).toEqual(before);
    const migrated = await Effect.runPromise(database.one("SELECT revision, indexed_revision, generation FROM chat_search_progress"));
    await insertMessages(database, 31, 1);
    const pending = await Effect.runPromise(database.one("SELECT revision, indexed_revision, generation FROM chat_search_progress"));
    expect(pending?.["revision"]).toBe(Number(migrated?.["revision"]) + 1);
    expect(pending?.["indexed_revision"]).toBe(migrated?.["indexed_revision"]);
    expect(pending?.["generation"]).toBe(migrated?.["generation"]);
    const schemaVersion = await Effect.runPromise(database.one("PRAGMA schema_version"));
    await Effect.runPromise(initializeDatabase(database));
    expect(await Effect.runPromise(database.one("PRAGMA schema_version"))).toEqual(schemaVersion);
    await app.run(bot.workers.search.index([-1007]));
    const complete = await Effect.runPromise(database.one("SELECT revision, indexed_revision, end_message_id FROM chat_search_progress"));
    expect(complete?.["end_message_id"]).toBe(31);
    expect(complete?.["revision"]).toBe(complete?.["indexed_revision"]);
  } finally {
    await app.close();
    database.close();
  }
});
