import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, richContent } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");
const presence = () => [FakeBotApiReply.ok(true), FakeBotApiReply.ok(true)] as const;

test("block command prevents the selected user from using one command", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate("/block 77 weather", 301)));
  } finally {
    await app.close();
  }
  const row = await Effect.runPromise(database.one(
    "SELECT user_id, command, blocked_by FROM command_blocklist",
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(row?.["user_id"]).toBe(77);
  expect(row?.["command"]).toBe("weather");
  expect(row?.["blocked_by"]).toBe(1);
  expect(reply?.params).toMatchObject({
    text: "✅ User <code>77</code> blocked from using /weather",
  });
});

test("blocklist presents moderation records in a native rich table", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());
  await Effect.runPromise(database.execute(
    "INSERT INTO command_blocklist (user_id, command, blocked_by) VALUES (?, ?, ?)",
    [77, "weather", 1],
  ));

  try {
    await app.run(bot.handler(commandUpdate("/blocklist", 304)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("77\n/weather\n1");
  expect(content.types).toContain("table");
});

test("unblock command reports when no matching block exists", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate("/unblock 88 search", 302)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({
    text: "❓ User <code>88</code> was not blocked from /search",
  });
});

test("whitelist command enables one command for the current chat", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate("/whitelist ask", 303)));
  } finally {
    await app.close();
  }
  const row = await Effect.runPromise(database.one(
    "SELECT command, whitelist_type, whitelist_id FROM command_whitelist",
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(row?.["command"]).toBe("ask");
  expect(row?.["whitelist_type"]).toBe("chat");
  expect(row?.["whitelist_id"]).toBe(-1007);
  expect(reply?.params).toMatchObject({
    text: "✅ Added chat <code>-1007</code> for /ask",
  });
});
