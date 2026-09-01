import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture } from "./harness.ts";

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
    await app.run(bot.handler(commandUpdate("/gstats", 402)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  const text = typeof reply?.params === "object" && reply.params !== null
    ? Reflect.get(reply.params, "text")
    : undefined;
  expect(text).toContain("66.7% - Ayaan");
  expect(text).toContain("33.3% - Alice");
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
    await app.run(bot.handler(commandUpdate("/friends", 403)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  const text = typeof reply?.params === "object" && reply.params !== null
    ? Reflect.get(reply.params, "text")
    : undefined;
  expect(text).toContain("2 ⟶ Alice");
  expect(text).toContain("1 ← Bob");
});
