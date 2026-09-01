import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, testConfig } from "./harness.ts";

test("tldr returns a cached YouTube summary without calling providers", async () => {
  let providerCalls = 0;
  const send: Fetch = async () => {
    providerCalls += 1;
    return new Response("{}");
  };
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ], config);
  await Effect.runPromise(database.batch([
    { sql: "INSERT INTO command_whitelist (command, whitelist_type, whitelist_id) VALUES ('tldr', 'chat', -1007)" },
    { sql: "INSERT INTO tldw (video_id, summary, user_id) VALUES (?, ?, ?)", args: ["abc123", "- Cached answer", 1] },
  ]));
  const base = commandUpdate("/tldr https://youtu.be/abc123", 1_001);
  if (base.message === undefined) throw new Error("Expected command message");
  const update: Update = {
    ...base,
    message: {
      ...base.message,
      entities: [
        { length: 5, offset: 0, type: "bot_command" },
        { length: 25, offset: 6, type: "url" },
      ],
    },
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  const text = typeof reply?.params === "object" && reply.params !== null
    ? Reflect.get(reply.params, "text")
    : undefined;
  expect(providerCalls).toBe(0);
  expect(text).toContain("Cached answer");
});
