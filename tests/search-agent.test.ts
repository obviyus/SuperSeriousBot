import { afterAll, beforeAll, expect, test } from "bun:test";
import { Database as Sqlite } from "bun:sqlite";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { AppConfig } from "../src/app/config.ts";
import { answerSearch, checkQuery, runQuery } from "../src/features/search-agent.ts";
import { searchStorePath, syncSearchStores } from "../src/features/search-store.ts";
import { commandUpdate, fixture, sentMessage, testConfig } from "./harness.ts";

type Call = { readonly name: string; readonly input: unknown };

// A fake OpenRouter chat-completions endpoint that plays scripted tool calls
// to Pi as a stream and records every request it receives.
function fakeOpenRouter(steps: ReadonlyArray<ReadonlyArray<Call>>) {
  const bodies: Array<string> = [];
  const server = Bun.serve({
    fetch: async (request) => {
      bodies.push(await request.text());
      const calls = steps[bodies.length - 1] ?? [];
      const chunk = (delta: unknown, finish: string | null) => `data: ${JSON.stringify({
        choices: [{ delta, finish_reason: finish, index: 0 }],
        created: 1,
        id: "chatcmpl-test",
        model: "test/model",
        object: "chat.completion.chunk",
      })}\n\n`;
      const events = calls.length === 0
        ? [chunk({ content: "done", role: "assistant" }, null), chunk({}, "stop")]
        : [
            chunk({
              role: "assistant",
              tool_calls: calls.map((call, index) => ({
                function: { arguments: JSON.stringify(call.input), name: call.name },
                id: `call_${bodies.length}_${index}`,
                index,
                type: "function",
              })),
            }, null),
            chunk({}, "tool_calls"),
          ];
      return new Response([...events, "data: [DONE]\n\n"].join(""), {
        headers: { "content-type": "text/event-stream" },
      });
    },
    port: 0,
  });
  return { bodies, server, url: `http://127.0.0.1:${server.port}/api/v1` };
}

let state = "";
beforeAll(async () => {
  state = await mkdtemp(join(tmpdir(), "ssb-search-"));
});
afterAll(async () => {
  await rm(state, { force: true, recursive: true });
});

function config(baseUrl: string, excluded: ReadonlyArray<string> = []): AppConfig {
  return {
    ...testConfig({ openrouterApiKey: "test", openrouterBaseUrl: baseUrl }),
    searchExcludedUsers: new Set(excluded),
    stateDirectory: state,
  };
}

async function seed(database: Awaited<ReturnType<typeof fixture>>["database"]) {
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO group_settings (chat_id, fts) VALUES (-1007, 1), (-1008, 1)" },
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (7, 'Nathuram', 'Nathu'), (8, 'alice', 'Alice'), (44, 'MyTransformerIsFine', 'S')" },
    { sql: `INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES
      (-1007, 8, 98, 'is he a Jensen fan?', '2026-11-16 14:45:00'),
      (-1007, 7, 100, 'hero worship is always cringe to me', '2026-11-16 14:45:14'),
      (-1007, 8, 150, 'my hero is Batman', '2026-11-16 14:46:00'),
      (-1007, 44, 151, 'OPTED OUT hero', '2026-11-16 14:47:00'),
      (-1007, 8, NULL, NULL, '2021-01-01 00:00:00'),
      (-1007, 9, 50, 'left the group years ago', '2018-03-01 00:00:00'),
      (-1008, 7, 101, 'OTHER CHAT hero', '2026-11-16 14:45:00')` },
    { sql: "INSERT INTO chat_mentions (chat_id, mentioning_user_id, mentioned_user_id, message_id) VALUES (-1007, 8, 7, 98), (-1007, 8, 44, 150), (-1008, 7, 8, 101)" },
    { sql: "INSERT INTO chat_aliases (chat_id, user_id, alias, confidence, update_time) VALUES (-1007, 7, 'nathu', 1, '2026-01-01'), (-1007, 44, 'OPTED OUT ALIAS', 1, '2026-01-01')" },
    { sql: "INSERT INTO chat_personas (chat_id, user_id, sheet, receipts, source_end_message_id, update_time) VALUES (-1007, 7, 'Nathu is a contrarian', '[]', 100, '2026-01-01'), (-1007, 44, 'OPTED OUT PERSONA', '[]', 151, '2026-01-01')" },
  ]));
}

test("search store copies one chat without opted-out members and syncs only new rows", async () => {
  const { app, database, dependencies } = await fixture(async () => new Response("{}"), [], config("http://unused", ["mytransformerisfine"]));
  await seed(database);
  try {
    await Effect.runPromise(syncSearchStores(dependencies));
    await Effect.runPromise(database.execute(
      "INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES (-1007, 7, 160, 'new hero line', '2026-11-16 15:00:00')",
    ));
    await Effect.runPromise(syncSearchStores(dependencies, [-1007]));
  } finally {
    await app.close();
    database.close();
  }
  const store = new Sqlite(searchStorePath(state, -1007), { readonly: true });
  try {
    const dump = JSON.stringify([
      store.query("SELECT * FROM messages").all(),
      store.query("SELECT * FROM members").all(),
      store.query("SELECT * FROM interactions").all(),
    ]);
    expect(dump).not.toContain("OPTED OUT");
    expect(dump).not.toContain("OTHER CHAT");
    expect(store.query("SELECT message_id FROM messages ORDER BY message_id").all()).toEqual([
      { message_id: 50 }, { message_id: 98 }, { message_id: 100 }, { message_id: 150 }, { message_id: 160 },
    ]);
    expect(store.query(
      "SELECT m.message_id FROM messages_fts f JOIN messages m ON m.message_id = f.rowid WHERE messages_fts MATCH 'hero*' AND m.user_id = 7 ORDER BY m.message_id",
    ).all()).toEqual([{ message_id: 100 }, { message_id: 160 }]);
    expect(store.query("SELECT user_id, username, aliases, profile, message_count FROM members WHERE user_id = 7").get()).toEqual({
      aliases: "[\"nathu\"]", message_count: 2, profile: "Nathu is a contrarian", user_id: 7, username: "Nathuram",
    });
    expect(store.query("SELECT author, text FROM message_log WHERE message_id = 100").get()).toEqual({
      author: "Nathu", text: "hero worship is always cringe to me",
    });
    expect(store.query("SELECT * FROM interactions").all()).toEqual([
      { mentions_or_replies: 1, other_user_id: 7, user_id: 8 },
    ]);
  } finally {
    store.close();
  }
});

test("agent queries run unrestricted on a read-only copy but cannot open other files", async () => {
  expect(checkQuery("ATTACH '/app/db/telly-jobs.db' AS jobs")).toBeString();
  expect(checkQuery("SELECT load_extension('x')")).toBeString();
  expect(checkQuery("PRAGMA table_info(messages)")).toBeUndefined();

  const path = join(state, "query.db");
  const store = new Sqlite(path, { create: true });
  store.exec("CREATE TABLE messages (message_id INTEGER PRIMARY KEY, text TEXT)");
  const insert = store.prepare("INSERT INTO messages VALUES (?, ?)");
  for (let id = 1; id <= 500; id += 1) insert.run(id, "x".repeat(1_000));
  store.close();
  const all = await runQuery(path, "SELECT * FROM messages");
  expect(all.rows).toHaveLength(500);
  expect(all.rows?.[0]).toEqual({ message_id: 1, text: "x".repeat(1_000) });
  expect((await runQuery(path, "DELETE FROM messages")).error).toBeString();
  expect(new Sqlite(path).query("SELECT count(*) AS n FROM messages").get()).toEqual({ n: 500 });
  const stopped = new AbortController();
  stopped.abort();
  expect(await runQuery(path, "SELECT * FROM messages", stopped.signal)).toEqual({ error: "The search ended before this query finished." });
});

test("active members are regular recent posters still in the group", async () => {
  const member = (id: number, status: string) => FakeBotApiReply.ok({ status, user: { first_name: `u${id}`, id, is_bot: false } });
  const { app, bot, database, dependencies } = await fixture(
    async () => new Response("{}"),
    [member(7, "member"), member(8, "left"), member(9, "member")],
    config("http://127.0.0.1:9"),
  );
  await seed(database);
  try {
    await Effect.runPromise(syncSearchStores(dependencies, [-1007]));
    const writable = new Sqlite(searchStorePath(state, -1007));
    const insert = writable.prepare("INSERT INTO messages (message_id, user_id, time, text) VALUES (?, ?, datetime('now', '-1 day'), 'hi')");
    for (let index = 0; index < 25; index += 1) {
      insert.run(10_000 + index, 7);
      insert.run(20_000 + index, 8);
    }
    writable.close();
    await app.run(bot.workers.search.membership([-1007]));
    const store = new Sqlite(searchStorePath(state, -1007), { readonly: true });
    // 7 posts and is in; 8 posts but left; 9 last posted in 2018.
    expect(store.query("SELECT user_id FROM active_members").all()).toEqual([{ user_id: 7 }]);
    expect(store.query("SELECT user_id, status FROM membership ORDER BY user_id").all()).toEqual([
      { status: "member", user_id: 7 }, { status: "left", user_id: 8 }, { status: "member", user_id: 9 },
    ]);
    // A failed lookup (44 has no reply queued) records nothing.
    expect(store.query("SELECT count(*) AS n FROM members WHERE user_id NOT IN (SELECT user_id FROM membership)").get()).toEqual({ n: 1 });
    store.close();
  } finally {
    await app.close();
    database.close();
  }
});

test("search agent runs Pi with only the sql and answer tools and cites only returned messages", async () => {
  const openRouter = fakeOpenRouter([
    [{ input: { sql: "SELECT m.message_id, m.text FROM messages_fts f JOIN messages m ON m.message_id = f.rowid WHERE messages_fts MATCH 'hero*' AND m.user_id = 7" }, name: "sql" }],
    [{ input: { answer: "Nobody. Nathu thinks hero worship is cringe.", citations: [100, 999] }, name: "answer" }],
  ]);
  const { app, database, dependencies } = await fixture(async () => new Response("{}"), [], config(openRouter.url, ["mytransformerisfine"]));
  await seed(database);
  try {
    await Effect.runPromise(syncSearchStores(dependencies));
    const result = await Effect.runPromise(answerSearch(
      dependencies, "who is nathu's hero", -1007, searchStorePath(state, -1007),
    ));
    const first = JSON.parse(openRouter.bodies[0] ?? "{}") as { tools?: Array<{ function: { name: string } }> };
    expect(first.tools?.map((item) => item.function.name).sort()).toEqual(["answer", "sql"]);
    expect(openRouter.bodies[0]).toContain("who is nathu's hero");
    expect(openRouter.bodies[1]).toContain("hero worship is always cringe to me");
    expect(openRouter.bodies.join("\n")).not.toContain("OPTED OUT");
    expect(result.citations).toEqual([100]);
    expect(result.answer).toContain("Nobody. Nathu thinks hero worship is cringe.");
    expect(result.answer).toContain("https://t.me/c/7/100");
  } finally {
    openRouter.server.stop(true);
    await app.close();
    database.close();
  }
});

test("search command syncs the chat copy, replies with the agent answer and logs it", async () => {
  const openRouter = fakeOpenRouter([
    [{ input: { sql: "SELECT message_id, text FROM messages ORDER BY message_id DESC LIMIT 5" }, name: "sql" }],
    [{ input: { answer: "Nathu just posted a new hero line.", citations: [160] }, name: "answer" }],
  ]);
  const { app, bot, database, fake } = await fixture(async () => new Response("{}"), [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(501),
    FakeBotApiReply.ok(true),
  ], config(openRouter.url));
  await seed(database);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO command_whitelist (command, whitelist_type, whitelist_id) VALUES ('search', 'chat', -1007)" },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES (-1007, 7, 160, 'new hero line', '2026-11-16 15:00:00')" },
  ]));
  try {
    await app.run(bot.handler(commandUpdate("/search what did nathu just say", 5_001)));
  } finally {
    openRouter.server.stop(true);
    await app.close();
  }
  const event = await Effect.runPromise(database.one(
    "SELECT citation_message_ids, lane FROM search_events WHERE message_id = ?",
    [5_001],
  ));
  database.close();

  expect(openRouter.bodies[1]).toContain("new hero line");
  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const text = String(Reflect.get(Reflect.get(Object(reply?.params), "rich_message"), "markdown"));
  expect(text).toContain("Nathu just posted a new hero line.");
  expect(text).toContain("https://t.me/c/7/160");
  expect(event).toMatchObject({ citation_message_ids: "[160]", lane: "agent" });
});
