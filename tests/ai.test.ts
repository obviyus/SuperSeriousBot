import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, sentMessage, testConfig } from "./harness.ts";

function aiConfig() {
  return {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
}

async function allow(database: Awaited<ReturnType<typeof fixture>>["database"], command: string) {
  await Effect.runPromise(database.execute(
    `INSERT INTO command_whitelist (command, whitelist_type, whitelist_id)
     VALUES (?, 'chat', ?)`,
    [command, -1007],
  ));
}

test("ask command streams the OpenRouter answer into Telegram", async () => {
  const send: Fetch = async (_input, init) => {
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    expect(body.model).toBe("x-ai/grok-4.3");
    expect(body.stream).toBe(true);
    return new Response(
      `data: {"choices":[{"delta":{"content":"Hello from AI"}}]}\n\ndata: [DONE]\n\n`,
      { headers: { "content-type": "text/event-stream" } },
    );
  };
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    await app.run(bot.handler(commandUpdate("/ask hello", 901)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  const text = typeof reply?.params === "object" && reply.params !== null
    ? Reflect.get(reply.params, "text")
    : undefined;
  expect(text).toContain("Hello from AI");
});

test("ask command stops before OpenRouter after its daily limit", async () => {
  let providerCalls = 0;
  const send: Fetch = async () => {
    providerCalls += 1;
    return new Response(
      `data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n`,
    );
  };
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    for (let count = 0; count < 41; count += 1) {
      await app.run(bot.handler(commandUpdate(`/ask request ${count}`, 910 + count)));
    }
  } finally {
    await app.close();
  }
  const usage = await Effect.runPromise(database.one(
    "SELECT current_usage FROM user_command_limits WHERE user_id = 1 AND command = 'ask'",
  ));
  database.close();

  const messages = fake.requests.filter((request) => request.method === "sendMessage");
  expect(providerCalls).toBe(40);
  expect(usage?.["current_usage"]).toBe(40);
  expect(messages.at(-1)?.params).toMatchObject({
    text: "Daily limit for this command reached. Try again tomorrow.",
  });
});

test("edit command sends the generated OpenRouter image", async () => {
  const send: Fetch = async () => new Response(JSON.stringify({
    data: [{ b64_json: Buffer.from("generated-image").toString("base64") }],
  }));
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(97),
  ], aiConfig());
  await allow(database, "edit");

  try {
    await app.run(bot.handler(commandUpdate("/edit tiny moon", 902)));
  } finally {
    await app.close();
    database.close();
  }

  const photo = fake.requests.find((request) => request.method === "sendPhoto");
  expect(photo?.contentType).toBe("multipart/form-data");
  expect(Object.values(photo?.files ?? {})[0]?.size).toBe(15);
  expect(photo?.params).toMatchObject({ caption: expect.stringContaining("tiny moon") });
});
