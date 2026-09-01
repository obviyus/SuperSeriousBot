import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, sentMessage } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

function withPhoto(text: string, updateId: number): Update {
  const update = commandUpdate(text, updateId);
  if (update.message === undefined) throw new Error("Expected command message");
  return {
    ...update,
    message: {
      ...update.message,
      replyToMessage: {
        chat: update.message.chat,
        date: 1_699_999_999,
        from: { firstName: "Alice", id: 2, isBot: false, username: "alice" },
        messageId: updateId - 1,
        photo: [{
          fileId: "photo-file-id",
          fileSize: 123,
          fileUniqueId: "photo-unique-id",
          height: 100,
          width: 100,
        }],
      },
    },
  };
}

test("set command stores replied media with its Telegram identity", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);

  try {
    await app.run(bot.handler(withPhoto("/set portrait", 501)));
  } finally {
    await app.close();
  }
  const stored = await Effect.runPromise(database.one(
    "SELECT key, file_id, file_unique_id, type FROM object_store",
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(stored?.["key"]).toBe("portrait");
  expect(stored?.["file_id"]).toBe("photo-file-id");
  expect(stored?.["file_unique_id"]).toBe("photo-unique-id");
  expect(stored?.["type"]).toBe("PHOTO");
  expect(reply?.params).toMatchObject({ text: expect.stringContaining("saved") });
});

test("get command sends stored media and increments its fetch count", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(93),
  ]);
  await Effect.runPromise(database.execute(
    `INSERT INTO object_store (key, file_id, file_unique_id, user_id, type)
     VALUES (?, ?, ?, ?, ?)`,
    ["portrait", "photo-file-id", "photo-unique-id", 1, "PHOTO"],
  ));

  try {
    await app.run(bot.handler(commandUpdate("/get portrait", 502)));
  } finally {
    await app.close();
  }
  const stored = await Effect.runPromise(database.one(
    "SELECT fetch_count FROM object_store WHERE key = ?",
    ["portrait"],
  ));
  database.close();

  const photo = fake.requests.find((request) => request.method === "sendPhoto");
  expect(photo?.params).toMatchObject({ photo: "photo-file-id" });
  expect(stored?.["fetch_count"]).toBe(1);
});

test("addquote forwards the replied message and saves its archive identity", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(700),
  ]);
  const update = commandUpdate("/addquote", 503);
  if (update.message === undefined) throw new Error("Expected command message");
  const quoted: Update = {
    ...update,
    message: {
      ...update.message,
      replyToMessage: {
        chat: update.message.chat,
        date: 1_699_999_999,
        from: { firstName: "Alice", id: 2, isBot: false, username: "alice" },
        messageId: 499,
        text: "Worth remembering",
      },
    },
  };

  try {
    await app.run(bot.handler(quoted));
  } finally {
    await app.close();
  }
  const stored = await Effect.runPromise(database.one(
    "SELECT message_id, message_user_id, saver_user_id, forwarded_message_id FROM quote_db",
  ));
  database.close();

  const forwarded = fake.requests.find((request) => request.method === "forwardMessage");
  expect(forwarded?.params).toMatchObject({
    chat_id: -1001,
    from_chat_id: -1007,
    message_id: 499,
  });
  expect(stored?.["message_user_id"]).toBe(2);
  expect(stored?.["saver_user_id"]).toBe(1);
  expect(stored?.["forwarded_message_id"]).toBe(700);
});
