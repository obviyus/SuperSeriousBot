import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

test("remind command parses relative time and preserves the title", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);

  try {
    await app.run(bot.handler(commandUpdate("/remind Make tea - in 2 hours", 801)));
  } finally {
    await app.close();
  }
  const row = await Effect.runPromise(database.one(
    "SELECT title, target_time FROM reminders",
  ));
  database.close();

  expect(row?.["title"]).toBe("Make tea");
  expect(row?.["target_time"]).toBe(1_788_271_200);
  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: expect.stringContaining("Make tea") });
});

test("reminder worker sends and removes each claimed reminder", async () => {
  const { app, bot, database, fake } = await fixture(offline);
  await Effect.runPromise(database.execute(
    "INSERT INTO reminders (chat_id, user_id, title, target_time) VALUES (?, ?, ?, ?)",
    [-1007, 1, "Stand up", 1_788_261_199],
  ));

  try {
    await app.run(bot.workers.reminders());
  } finally {
    await app.close();
  }
  const remaining = await Effect.runPromise(database.one("SELECT 1 FROM reminders"));
  database.close();

  const sent = fake.requests.find((request) => request.method === "sendMessage");
  expect(sent?.params).toMatchObject({
    chat_id: -1007,
    text: expect.stringContaining("Stand up"),
  });
  expect(remaining).toBeUndefined();
});

test("reminder worker parks a reminder after five failed deliveries", async () => {
  const offline: Fetch = async () => new Response("{}");
  const failures = Array.from({ length: 5 }, () => FakeBotApiReply.reject({
    description: "Forbidden: bot was blocked by the user",
    errorCode: 403,
  }));
  const { app, bot, database } = await fixture(offline, failures);
  await Effect.runPromise(database.execute(
    "INSERT INTO reminders (id, chat_id, user_id, title, target_time) VALUES (?, ?, ?, ?, ?)",
    [92, -1007, 1, "Unreachable", 1],
  ));

  try {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await app.run(bot.workers.reminders());
      await Effect.runPromise(database.execute(
        "UPDATE reminders SET claim_time = 1 WHERE id = ?",
        [92],
      ));
    }
    await app.run(bot.workers.reminders());
  } finally {
    await app.close();
  }
  const reminder = await Effect.runPromise(database.one(
    "SELECT attempt_count, last_error FROM reminders WHERE id = ?",
    [92],
  ));
  database.close();

  expect(reminder?.["attempt_count"]).toBe(5);
  expect(reminder?.["last_error"]).toContain("bot was blocked by the user");
});
