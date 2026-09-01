import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, sentMessage } from "./harness.ts";

test("shiba command sends the image returned by Dog CEO", async () => {
  const send: Fetch = async () => new Response(JSON.stringify({
    message: "https://images.example/shiba.jpg",
    status: "success",
  }), { headers: { "content-type": "application/json" } });
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(91),
  ]);

  try {
    await app.run(bot.handler(commandUpdate("/shiba", 81)));
  } finally {
    await app.close();
    database.close();
  }

  const photo = fake.requests.find((request) => request.method === "sendPhoto");
  expect(photo?.params).toMatchObject({
    chat_id: -1007,
    photo: "https://images.example/shiba.jpg",
  });
});

test("meme command skips unsafe results before sending a photo", async () => {
  let calls = 0;
  const send: Fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify(calls === 1
      ? { nsfw: true, url: "https://images.example/unsafe.jpg" }
      : { nsfw: false, url: "https://images.example/safe.jpg" }), {
      headers: { "content-type": "application/json" },
    });
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(92),
  ]);

  try {
    await app.run(bot.handler(commandUpdate("/meme", 82)));
  } finally {
    await app.close();
    database.close();
  }

  const photo = fake.requests.find((request) => request.method === "sendPhoto");
  expect(calls).toBe(2);
  expect(photo?.params).toMatchObject({ photo: "https://images.example/safe.jpg" });
});

test("insult command gives a polite fallback when its provider is unavailable", async () => {
  const send: Fetch = async () => {
    throw new Error("network unavailable");
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);

  try {
    await app.run(bot.handler(commandUpdate("/insult", 83)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: "I'm too polite to insult right now." });
});

test("blocked command stops before its provider and records the outcome", async () => {
  let providerCalls = 0;
  const send: Fetch = async () => {
    providerCalls += 1;
    return new Response("{}");
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);
  await Effect.runPromise(database.execute(
    "INSERT INTO command_blocklist (user_id, command, blocked_by) VALUES (?, ?, ?)",
    [1, "fox", 9],
  ));

  try {
    await app.run(bot.handler(commandUpdate("/fox", 84)));
  } finally {
    await app.close();
  }
  const event = await Effect.runPromise(database.one(
    "SELECT status FROM command_stats WHERE message_id = ?",
    [84],
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(providerCalls).toBe(0);
  expect(reply?.params).toMatchObject({ text: "❌ You are blocked from using this command." });
  expect(event?.["status"]).toBe("blocked");
});
