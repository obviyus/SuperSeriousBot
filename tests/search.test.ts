import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import {
  buildUtterances,
  buildWindows,
  renderSearchAnswer,
  selectEvidence,
  type SourceMessage,
} from "../src/features/search.ts";
import {
  commandUpdate,
  fixture,
  openRouterEmbeddings,
  openRouterText,
  sentMessage,
  testConfig,
} from "./harness.ts";

const model = "qwen/qwen3-embedding-8b";

function messages(count: number): ReadonlyArray<SourceMessage> {
  return Array.from({ length: count }, (_, index) => ({
    author: index < 2 ? "@alice" : "@bob",
    createTime: `2026-08-08T10:${String(index).padStart(2, "0")}:00Z`,
    messageId: index + 1,
    text: `message ${index + 1}`,
    userId: index < 2 ? 1 : 2,
  }));
}

test("search windows overlap while utterances retain speaker ownership", () => {
  const source = messages(29);

  const windows = buildWindows(source);
  const utterances = buildUtterances(source.slice(0, 3));

  expect(windows.map((window) => [window.startMessageId, window.endMessageId])).toEqual([
    [1, 24],
    [9, 29],
    [17, 29],
    [25, 29],
  ]);
  expect(utterances.map((item) => [item.userId, item.startMessageId, item.endMessageId])).toEqual([
    [1, 1, 2],
    [2, 3, 3],
  ]);
});

test("search evidence removes overlaps and owns valid citation links", () => {
  const evidence = [
    { citationMessageId: 24, endMessageId: 24, endTime: "b", messageCount: 24, score: 0.8, startMessageId: 1, startTime: "a", text: "first" },
    { citationMessageId: 32, endMessageId: 32, endTime: "d", messageCount: 24, score: 0.7, startMessageId: 9, startTime: "c", text: "overlap" },
    { citationMessageId: 124, endMessageId: 124, endTime: "f", messageCount: 24, score: 0.6, startMessageId: 100, startTime: "e", text: "third" },
  ];

  const selected = selectEvidence(evidence);
  const rendered = renderSearchAnswer(
    { answer: "Alice has the strongest receipts.", citations: [2, 1, 2] },
    selected,
    -1_001_234_567_890,
  );

  expect(selected.map((item) => item.text)).toEqual(["first", "third"]);
  expect(rendered).toEqual({
    answer: "Alice has the strongest receipts.\n\n[2](https://t.me/c/1234567890/124) [1](https://t.me/c/1234567890/24)",
    citations: [124, 24],
  });
  expect(renderSearchAnswer(
    { answer: "An uncited claim", citations: [] },
    selected,
    -1_001_234_567_890,
  ).answer).toBe("No solid answer in the chat.");
});

test("search index replaces growing tail windows", async () => {
  const send: Fetch = async (_input, init) => openRouterEmbeddings(String(init?.body));
  const config = testConfig({ openrouterApiKey: "openrouter-test" });
  const { app, bot, database } = await fixture(send, [], config);
  await Effect.runPromise(database.batch([
    { args: [-1007], sql: "INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)" },
    ...messages(30).map((message) => ({
      args: [-1007, message.userId, message.messageId, message.createTime, message.text],
      sql: `INSERT INTO chat_stats (
        chat_id, user_id, message_id, create_time, message_text
      ) VALUES (?, ?, ?, ?, ?)`,
    })),
  ]));

  try {
    await app.run(bot.workers.search.index());
    await Effect.runPromise(database.batch(messages(40).slice(30).map((message) => ({
      args: [-1007, message.userId, message.messageId, message.createTime, message.text],
      sql: `INSERT INTO chat_stats (
        chat_id, user_id, message_id, create_time, message_text
      ) VALUES (?, ?, ?, ?, ?)`,
    }))));
    await app.run(bot.workers.search.index());
  } finally {
    await app.close();
  }
  const windows = await Effect.runPromise(database.all(
    `SELECT start_message_id, end_message_id, message_count
     FROM chat_search_windows ORDER BY start_message_id`,
  ));
  const utterances = await Effect.runPromise(database.all(
    `SELECT start_message_id, end_message_id, user_id
     FROM chat_search_utterances ORDER BY start_message_id`,
  ));
  database.close();

  expect(windows.map((row) => [row["start_message_id"], row["end_message_id"]])).toEqual([
    [1, 24],
    [9, 32],
    [17, 40],
    [25, 40],
    [33, 40],
  ]);
  expect(utterances.at(-1)).toMatchObject({ end_message_id: 40, user_id: 2 });
});

test("search command answers from indexed evidence with a Telegram citation", async () => {
  let modelMessages = "";
  const send: Fetch = async (input, init) => {
    if (String(input).includes("embeddings")) return openRouterEmbeddings(String(init?.body));
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    modelMessages = JSON.stringify(body.messages);
    return openRouterText(JSON.stringify({
        answer: "Nathu is a product designer.",
        citations: [1],
      }));
  };
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(501),
    FakeBotApiReply.ok(true),
  ], config);
  const vector = JSON.stringify(Array(1_024).fill(0.01));
  await Effect.runPromise(database.batch([
    { args: ["search", -1007], sql: "INSERT INTO command_whitelist (command, whitelist_type, whitelist_id) VALUES (?, 'chat', ?)" },
    { args: [-1007], sql: "INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)" },
    {
      args: [-1007, 10, 24, "2026-01-01", "2026-01-02", 15, "24 @nathu: I design products", vector, model],
      sql: `INSERT INTO chat_search_windows (
        chat_id, start_message_id, end_message_id, start_time, end_time,
        message_count, message_text, embedding, embedding_model, embedding_dimension
      ) VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 1024)`,
    },
  ]));

  try {
    await app.run(bot.handler(commandUpdate("/search what does Nathu do", 5_001)));
  } finally {
    await app.close();
  }
  const event = await Effect.runPromise(database.one(
    "SELECT answer, citation_message_ids FROM search_events WHERE message_id = ?",
    [5_001],
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const params = reply?.params;
  if (typeof params !== "object" || params === null) throw new Error("Search reply missing");
  const text = Reflect.get(Reflect.get(params, "rich_message"), "markdown");
  expect(modelMessages).toContain("Telegram Rich Markdown");
  expect(text).toContain("Nathu is a product designer.");
  expect(text).toContain("https://t.me/c/7/24");
  expect(event).toMatchObject({ citation_message_ids: "[24]" });
});

test("import command stores Telegram JSON messages and enables search", async () => {
  const exportBytes = new TextEncoder().encode(JSON.stringify({
    messages: [
      { date: "2026-08-01T10:00:00", from_id: "user7", id: 77, text: "hello", type: "message" },
      { date: "2026-08-01T10:01:00", from_id: "user8", id: 78, text: ["rich ", { text: "text", type: "bold" }], type: "message" },
      { date: "2026-08-01T10:02:00", id: 79, text: "service", type: "service" },
    ],
  }));
  const offline: Fetch = async () => new Response("{}");
  const { app, bot, database } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(502),
    FakeBotApiReply.ok({
      file_id: "export-file",
      file_path: "exports/result.json",
      file_size: exportBytes.length,
      file_unique_id: "export-unique",
    }),
    FakeBotApiReply.file(exportBytes),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);
  const base = commandUpdate("/import", 5_002);
  if (base.message === undefined) throw new Error("Expected import message");
  const update: Update = {
    ...base,
    message: {
      ...base.message,
      replyToMessage: {
        chat: base.message.chat,
        date: base.message.date - 1,
        document: {
          fileId: "export-file",
          fileName: "result.json",
          fileSize: exportBytes.length,
          fileUniqueId: "export-unique",
          mimeType: "application/json",
        },
        messageId: 5_001,
      },
    },
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
  }
  const rows = await Effect.runPromise(database.all(
    "SELECT user_id, message_id, message_text FROM chat_stats ORDER BY message_id",
  ));
  const setting = await Effect.runPromise(database.one(
    "SELECT fts FROM group_settings WHERE chat_id = ?",
    [-1007],
  ));
  const command = await Effect.runPromise(database.one(
    "SELECT status FROM command_stats WHERE command = 'import' AND message_id = ?",
    [5_002],
  ));
  database.close();

  expect(rows).toEqual([
    expect.objectContaining({ message_id: 77, message_text: "hello", user_id: 7 }),
    expect.objectContaining({ message_id: 78, message_text: "rich text", user_id: 8 }),
  ]);
  expect(setting?.["fts"]).toBe(1);
  expect(command?.["status"]).toBe("completed");
});

test("memory worker stores filtered personas, aliases, and lore", async () => {
  let completion = 0;
  const send: Fetch = async () => {
    completion += 1;
    const content = completion === 1
      ? { aliases: [{ alias: "  NatHu  ", confidence: 0.9 }, { alias: "bro", confidence: 1 }], sheet: "Designs excellent products [msg:200, msg:999]" }
      : { items: [{ receipts: [200, 999], summary: "The group debates cameras.", topic: "camera-war" }] };
    return openRouterText(JSON.stringify(content));
  };
  const config = testConfig({ openrouterApiKey: "openrouter-test" });
  const { app, bot, database } = await fixture(send, [], config);
  const vector = JSON.stringify(Array(256).fill(0.01));
  const utterances = Array.from({ length: 200 }, (_, index) => ({
    args: [-1007, index + 1, index + 1, 7, "@ayaan", "2026-01-01", "2026-01-01", 1, `${index + 1} camera chat`, vector, model],
    sql: `INSERT INTO chat_search_utterances (
      chat_id, start_message_id, end_message_id, user_id, author, start_time,
      end_time, message_count, message_text, embedding, embedding_model, embedding_dimension
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 256)`,
  }));
  await Effect.runPromise(database.batch([
    { args: [-1007], sql: "INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)" },
    { args: [7, "ayaan"], sql: "INSERT INTO user_stats (user_id, username) VALUES (?, ?)" },
    {
      args: [-1007, "camera-war", "Earlier camera lore.", "[150]", 150],
      sql: `INSERT INTO chat_lore (
        chat_id, topic, summary, receipts, source_end_message_id, update_time
      ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)`,
    },
    ...utterances,
    {
      args: [-1007, 177, 200, "2026-01-01", "2026-01-01", 24, "200 @ayaan: camera chat", JSON.stringify(Array(1_024).fill(0.01)), model],
      sql: `INSERT INTO chat_search_windows (
        chat_id, start_message_id, end_message_id, start_time, end_time,
        message_count, message_text, embedding, embedding_model, embedding_dimension
      ) VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 1024)`,
    },
  ]));

  try {
    await app.run(bot.workers.search.memory());
  } finally {
    await app.close();
  }
  const persona = await Effect.runPromise(database.one(
    "SELECT sheet, receipts FROM chat_personas WHERE chat_id = ? AND user_id = ?",
    [-1007, 7],
  ));
  const aliases = await Effect.runPromise(database.all(
    "SELECT alias FROM chat_aliases WHERE chat_id = ?",
    [-1007],
  ));
  const lore = await Effect.runPromise(database.one(
    "SELECT topic, summary, receipts FROM chat_lore WHERE chat_id = ?",
    [-1007],
  ));
  database.close();

  expect(persona).toMatchObject({ receipts: "[200]", sheet: "Designs excellent products [msg:200]" });
  expect(aliases.map((row) => row["alias"])).toEqual(["nathu"]);
  expect(lore).toMatchObject({
    receipts: "[150,200]",
    summary: "The group debates cameras.",
    topic: "camera-war",
  });
});
