import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, richContent } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

test("message tracking stores stats and distinct mention edges", async () => {
  const { app, bot, database } = await fixture(offline);
  await Effect.runPromise(database.execute(
    "INSERT INTO group_settings (chat_id, fts) VALUES (?, ?)",
    [-1007, 1],
  ));
  await Effect.runPromise(database.execute(
    "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)",
    [2, "alice", "Alice"],
  ));
  const update: Update = {
    message: {
      chat: { id: -1007, title: "Telly Lab", type: "supergroup" },
      date: 1_700_000_000,
      entities: [{ length: 6, offset: 6, type: "mention" }],
      from: { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
      messageId: 401,
      replyToMessage: {
        chat: { id: -1007, type: "supergroup" },
        date: 1_699_999_999,
        from: { firstName: "Alice", id: 2, isBot: false, username: "alice" },
        messageId: 400,
      },
      text: "hello @alice",
    },
    updateId: 401,
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
  }
  const stored = await Effect.runPromise(database.one(
    "SELECT user_id, message_text, reply_to_message_id FROM chat_stats WHERE message_id = ?",
    [401],
  ));
  const mentions = await Effect.runPromise(database.all(
    "SELECT mentioning_user_id, mentioned_user_id FROM chat_mentions WHERE message_id = ?",
    [401],
  ));
  database.close();

  expect(stored?.["user_id"]).toBe(1);
  expect(stored?.["message_text"]).toBe("hello @alice");
  expect(stored?.["reply_to_message_id"]).toBe(400);
  expect(mentions.map((row) => [row["mentioning_user_id"], row["mentioned_user_id"]])).toEqual([
    [1, 2],
  ]);
});

test("group stats ranks members by their message share", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)", args: [1, "obviyus", "Ayaan"] },
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)", args: [2, "alice", "Alice"] },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id) VALUES (?, ?, ?)", args: [-1007, 1, 1] },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id) VALUES (?, ?, ?)", args: [-1007, 1, 2] },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id) VALUES (?, ?, ?)", args: [-1007, 2, 3] },
  ]));

  try {
    await app.run(bot.handler(commandUpdate("/stats all", 402)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("Ayaan\n2\n66.7%");
  expect(content.text).toContain("Alice\n1\n33.3%");
  expect(content.types).toContain("table");
});

test("friends command renders incoming and outgoing social edges", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)", args: [2, "alice", "Alice"] },
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)", args: [3, "bob", "Bob"] },
    { sql: "INSERT INTO chat_mentions (chat_id, mentioning_user_id, mentioned_user_id, message_id) VALUES (?, ?, ?, ?)", args: [-1007, 1, 2, 1] },
    { sql: "INSERT INTO chat_mentions (chat_id, mentioning_user_id, mentioned_user_id, message_id) VALUES (?, ?, ?, ?)", args: [-1007, 1, 2, 2] },
    { sql: "INSERT INTO chat_mentions (chat_id, mentioning_user_id, mentioned_user_id, message_id) VALUES (?, ?, ?, ?)", args: [-1007, 3, 1, 3] },
  ]));

  try {
    await app.run(bot.handler(commandUpdate("/stats friends", 403)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("→\nAlice\n2");
  expect(content.text).toContain("←\nBob\n1");
  expect(content.types).toContain("table");
});

function keyboardOf(params: unknown): ReadonlyArray<ReadonlyArray<{ text: string; callback_data: string }>> {
  const markup = typeof params === "object" && params !== null ? Reflect.get(params, "reply_markup") : undefined;
  const rows = typeof markup === "object" && markup !== null ? Reflect.get(markup, "inline_keyboard") : undefined;
  if (!Array.isArray(rows)) throw new Error("Stats reply has no keyboard");
  return rows;
}

test("stats buttons switch the same message between views", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)", args: [1, "obviyus", "Ayaan"] },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id) VALUES (?, ?, ?)", args: [-1007, 1, 1] },
    { sql: "INSERT INTO command_stats (command, user_id) VALUES (?, ?)", args: ["ask", 1] },
  ]));

  let edit: unknown;
  let first: ReadonlyArray<ReadonlyArray<{ text: string; callback_data: string }>> = [];
  try {
    await app.run(bot.handler(commandUpdate("/stats", 404)));
    const sent = fake.requests.find((request) => request.method === "sendRichMessage");
    first = keyboardOf(sent?.params);
    const botButton = first.flat().find((button) => button.text === "Bot");
    if (botButton === undefined) throw new Error("No Bot button");
    fake.enqueue(FakeBotApiReply.ok({ id: 123456, is_bot: true, first_name: "Test", username: "testbot" }));
    fake.enqueue(FakeBotApiReply.ok(true));
    fake.enqueue(FakeBotApiReply.ok(true));
    const callback: Update = {
      callbackQuery: {
        chatInstance: "stats-chat",
        data: botButton.callback_data,
        from: { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
        id: "stats-callback",
        message: {
          chat: { id: -1007, title: "Telly Lab", type: "supergroup" },
          date: 1_700_000_001,
          messageId: 91,
        },
      },
      updateId: 405,
    };
    await app.run(bot.handler(callback));
    edit = fake.requests.find((request) => request.method === "editMessageText")?.params;
  } finally {
    await app.close();
    database.close();
  }

  expect(first.map((row) => row.map((button) => button.text))).toEqual([
    ["• Today", "All time", "Me"],
    ["Friends", "Bot"],
  ]);
  const content = richContent(edit);
  expect(content.text).toContain("Users:");
  expect(content.text).toContain("/ask");
  expect(keyboardOf(edit)[1]?.map((button) => button.text)).toEqual(["Friends", "• Bot"]);
});

test("stats for a named member shows their weekly card", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO user_stats (user_id, username, first_name) VALUES (?, ?, ?)", args: [2, "alice", "Alice"] },
    { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id, create_time) VALUES (?, ?, ?, datetime('now'))", args: [-1007, 2, 1] },
  ]));

  try {
    await app.run(bot.handler(commandUpdate("/stats @Alice", 406)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("👤 alice");
  expect(content.text).toContain("Lifetime");
  expect(keyboardOf(reply?.params).flat().some((button) => button.text.startsWith("•"))).toBe(false);
});
