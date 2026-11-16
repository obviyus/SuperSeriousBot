import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { answerSearch } from "../src/features/search-agent.ts";
import {
  commandUpdate,
  fixture,
  openRouterEmbeddings,
  openRouterToolCalls,
  sentMessage,
  testConfig,
} from "./harness.ts";

type Step = ReadonlyArray<{ readonly name: string; readonly input: unknown }>;

// Plays the model's tool calls in order and records every request body.
function scripted(steps: ReadonlyArray<Step>) {
  const bodies: Array<string> = [];
  const send: Fetch = async (input, init) => {
    if (String(input).includes("embeddings")) return openRouterEmbeddings(String(init?.body));
    bodies.push(String(init?.body));
    const step = steps[bodies.length - 1] ?? [{ input: { answer: "late", citations: [] }, name: "finish" }];
    return openRouterToolCalls(...step);
  };
  return { bodies, send };
}

const vector = (size: number) => JSON.stringify(Array(size).fill(0.01));

test("search agent finds an exact line by keyword and cites only messages it saw", async () => {
  const { bodies, send } = scripted([
    [{ name: "search_messages", input: { terms: ["hero"], userIds: [7] } }],
    [{ name: "read_messages", input: { messageId: 100, before: 2, after: 1 } }],
    [{ name: "finish", input: { answer: "Nobody. Nathu thinks hero worship is cringe.", citations: [100, 999] } }],
  ]);
  const { app, database, dependencies } = await fixture(send, [], testConfig({ openrouterApiKey: "test" }));
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (7, 'Nathuram', 'Nathu'), (8, 'alice', 'Alice')" },
    { sql: `INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES
      (-1007, 8, 98, 'is he a Jensen fan?', datetime('now')),
      (-1007, 7, 100, 'hero worship is always cringe to me', datetime('now')),
      (-1007, 8, 150, 'my hero is Batman', datetime('now')),
      (-1008, 7, 101, 'OTHER CHAT hero', datetime('now'))` },
    { sql: "INSERT INTO chat_aliases (chat_id, user_id, alias, confidence, update_time) VALUES (-1007, 7, 'nathu', 1, '2026-01-01')" },
  ]));
  try {
    const result = await Effect.runPromise(answerSearch(dependencies, "who is nathu's hero", -1007));
    expect(bodies[0]).toContain("who is nathu's hero");
    expect(bodies[0]).toContain('\\"aliases\\":[\\"nathu\\"]');
    expect(bodies[1]).toContain("hero worship is always cringe to me");
    expect(bodies[1]).not.toContain("my hero is Batman");
    expect(bodies.join("\n")).not.toContain("OTHER CHAT");
    expect(bodies[2]).toContain("is he a Jensen fan?");
    expect(result.citations).toEqual([100]);
    expect(result.answer).toContain("Nobody. Nathu thinks hero worship is cringe.");
    expect(result.answer).toContain("https://t.me/c/7/100");
  } finally {
    await app.close();
    database.close();
  }
});

test("search agent answers roundups from every active member's profile without citations", async () => {
  const { bodies, send } = scripted([
    [{ name: "profiles", input: {} }],
    [{ name: "finish", input: { answer: "- **Alice** — Pikachu\n- **Bob** — Snorlax", citations: [] } }],
  ]);
  const { app, database, dependencies } = await fixture(send, [], testConfig({ openrouterApiKey: "test" }));
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username) VALUES (42, 'alice'), (43, 'bob'), (44, 'gone')" },
    { sql: `INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES
      (-1007, 42, 1, 'hi', datetime('now')), (-1007, 43, 2, 'yo', datetime('now')),
      (-1007, 44, 3, 'old', '2020-01-01')` },
    { sql: `INSERT INTO chat_personas (chat_id, user_id, sheet, receipts, source_end_message_id, update_time) VALUES
      (-1007, 42, 'ALICE SHEET', '[]', 1, '2026-01-01'), (-1007, 43, 'BOB SHEET', '[]', 2, '2026-01-01'),
      (-1007, 44, 'INACTIVE SHEET', '[]', 3, '2026-01-01')` },
  ]));
  try {
    const result = await Effect.runPromise(answerSearch(dependencies, "assign a Pokémon to each member", -1007));
    expect(bodies[1]).toContain("ALICE SHEET");
    expect(bodies[1]).toContain("BOB SHEET");
    expect(bodies[1]).not.toContain("INACTIVE SHEET");
    expect(result).toEqual({ answer: "- **Alice** — Pikachu\n- **Bob** — Snorlax", citations: [] });
  } finally {
    await app.close();
    database.close();
  }
});

test("search agent tools never return opted-out members or another chat", async () => {
  const { bodies, send } = scripted([
    [
      { name: "search_messages", input: { terms: ["hike"] } },
      { name: "search_messages", input: { terms: ["hike"], userIds: [44] } },
      { name: "semantic_search", input: { query: "hiking" } },
      { name: "semantic_search", input: { query: "hiking", userIds: [44] } },
      { name: "profiles", input: { userIds: [42, 44] } },
      { name: "interactions", input: { userId: 42 } },
      { name: "interactions", input: { userId: 44 } },
      { name: "recent_messages", input: {} },
      { name: "read_messages", input: { messageId: 91 } },
    ],
    [{ name: "finish", input: { answer: "Alice hikes.", citations: [90, 91] } }],
  ]);
  const config = {
    ...testConfig({ openrouterApiKey: "test" }),
    searchExcludedUsers: new Set(["mytransformerisfine"]),
  };
  const { app, database, dependencies } = await fixture(send, [], config);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (42, 'alice', 'Alice'), (44, 'MyTransformerIsFine', 'S')" },
    { sql: `INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES
      (-1007, 42, 90, 'I hike on Sundays', datetime('now')),
      (-1007, 44, 91, 'OPTED OUT hike', datetime('now')),
      (-1008, 42, 92, 'OTHER CHAT hike', datetime('now'))` },
    { sql: "INSERT INTO chat_aliases (chat_id, user_id, alias, confidence, update_time) VALUES (-1007, 44, 'OPTED OUT ALIAS', 1, '2026-01-01')" },
    { sql: "INSERT INTO chat_personas (chat_id, user_id, sheet, receipts, source_end_message_id, update_time) VALUES (-1007, 44, 'OPTED OUT PERSONA', '[]', 91, '2026-01-01')" },
    { sql: "INSERT INTO chat_mentions (chat_id, mentioning_user_id, mentioned_user_id, message_id) VALUES (-1007, 42, 44, 90), (-1007, 44, 42, 91)" },
    {
      args: [-1007, 90, 91, "2026-01-01", "2026-01-01", 2, "90 @alice: I hike\n91 @x: OPTED OUT", vector(1_024), "qwen/qwen3-embedding-8b"],
      sql: `INSERT INTO chat_search_windows (chat_id, start_message_id, end_message_id, start_time, end_time,
        message_count, message_text, embedding, embedding_model, embedding_dimension)
        VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 1024)`,
    },
  ]));
  try {
    const result = await Effect.runPromise(answerSearch(dependencies, "who hikes", -1007));
    expect(bodies.join("\n")).not.toContain("OPTED OUT");
    expect(bodies.join("\n")).not.toContain("OTHER CHAT");
    expect(bodies[1]).toContain("I hike on Sundays");
    expect(result.citations).toEqual([90]);

    const before = bodies.length;
    const replied = await Effect.runPromise(answerSearch(dependencies, "what does he say", -1007, 44));
    expect(replied.citations).toEqual([]);
    expect(bodies).toHaveLength(before);
  } finally {
    await app.close();
    database.close();
  }
});

test("search agent gives up cleanly when it never calls finish", async () => {
  const loop = Array.from({ length: 20 }, () => [{ name: "recent_messages", input: {} }]);
  const { bodies, send } = scripted(loop);
  const { app, database, dependencies } = await fixture(send, [], testConfig({ openrouterApiKey: "test" }));
  try {
    const result = await Effect.runPromise(answerSearch(dependencies, "anything", -1007));
    expect(result).toEqual({ answer: "You'll have to remind me of that one.", citations: [] });
    expect(bodies).toHaveLength(10);
  } finally {
    await app.close();
    database.close();
  }
});

test("search command replies with the agent answer and logs it", async () => {
  const { send } = scripted([
    [{ name: "recent_messages", input: {} }],
    [{ name: "finish", input: { answer: "Alice said hi.", citations: [5] } }],
  ]);
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(501),
    FakeBotApiReply.ok(true),
  ], testConfig({ openrouterApiKey: "test" }));
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO group_settings (chat_id, fts) VALUES (-1007, 1)" },
    { sql: "INSERT INTO command_whitelist (command, whitelist_type, whitelist_id) VALUES ('search', 'chat', -1007)" },
    { sql: "INSERT INTO user_stats (user_id, username) VALUES (42, 'alice')" },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id, message_text, create_time) VALUES (-1007, 42, 5, 'hi', datetime('now'))" },
  ]));
  try {
    await app.run(bot.handler(commandUpdate("/search what did alice say", 5_001)));
  } finally {
    await app.close();
  }
  const event = await Effect.runPromise(database.one(
    "SELECT answer, citation_message_ids, lane FROM search_events WHERE message_id = ?",
    [5_001],
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const text = String(Reflect.get(Reflect.get(Object(reply?.params), "rich_message"), "markdown"));
  expect(text).toContain("Alice said hi.");
  expect(text).toContain("https://t.me/c/7/5");
  expect(event).toMatchObject({ citation_message_ids: "[5]", lane: "agent" });
});
