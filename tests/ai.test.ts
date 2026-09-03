import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import {
  commandUpdate,
  fixture,
  openRouterStream,
  sentMessage,
  testConfig,
} from "./harness.ts";

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
    expect(body.plugins).toEqual([{ engine: "native", id: "web", max_results: 20 }]);
    expect(body.reasoning).toEqual({ effort: "high" });
    const messages = JSON.stringify(body.messages);
    expect(messages).toContain("Telegram Rich Markdown");
    expect(messages).toContain("Write prices with ISO currency codes such as USD 48,500");
    return openRouterStream("Hello from AI");
  };
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");
  await Effect.runPromise(database.execute(
    "INSERT INTO group_settings (chat_id, ask_thinking) VALUES (-1, 'high')",
  ));

  try {
    await app.run(bot.handler(commandUpdate("/ask hello", 901)));
  } finally {
    await app.close();
    database.close();
  }

  const preview = fake.requests.find((request) => request.method === "sendMessage");
  const final = fake.requests.find((request) => request.method === "editMessageText");
  expect(preview?.params).toMatchObject({ text: "Hello from AI" });
  expect(final?.params).toMatchObject({
    rich_message: { markdown: "Hello from AI" },
  });
});

test("ask command includes a replied rich answer as context", async () => {
  let submitted = "";
  const send: Fetch = async (_input, init) => {
    submitted = typeof init?.body === "string" ? init.body : "";
    return openRouterStream("Detailed answer");
  };
  const { app, bot, database } = await fixture(send, [], aiConfig());
  await allow(database, "ask");
  const base = commandUpdate("/ask give detailed use cases", 905);
  if (base.message === undefined) throw new Error("Expected ask message");
  const update = {
    ...base,
    message: {
      ...base.message,
      replyToMessage: {
        chat: base.message.chat,
        date: base.message.date - 1,
        from: { firstName: "Super Serious Bot", id: 2, isBot: true },
        messageId: 904,
        richMessage: {
          blocks: [{
            text: "Browser-based remote desktop only. No official SSH access.",
            type: "paragraph" as const,
          }],
        },
      },
    },
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(submitted).toContain("Reply context:");
  expect(submitted).toContain("Browser-based remote desktop only. No official SSH access.");
  expect(submitted).toContain("give detailed use cases");
});

test("ask command sends its captioned image with replied text context", async () => {
  const image = new TextEncoder().encode("watch-photo");
  let submitted = "";
  const send: Fetch = async (_input, init) => {
    submitted = typeof init?.body === "string" ? init.body : "";
    return openRouterStream("Identified watch");
  };
  const { app, bot, database } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok({
      file_id: "watch-photo",
      file_path: "photos/watch.jpg",
      file_size: image.length,
      file_unique_id: "watch-photo-unique",
    }),
    FakeBotApiReply.file(image),
    sentMessage(906),
    FakeBotApiReply.ok(true),
  ], aiConfig());
  await allow(database, "ask");
  const update: Update = {
    message: {
      caption: "/ask identify this watch",
      captionEntities: [{ length: 4, offset: 0, type: "bot_command" }],
      chat: { id: -1007, type: "supergroup" },
      date: 1_700_000_000,
      from: { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
      messageId: 906,
      photo: [{
        fileId: "watch-photo",
        fileSize: image.length,
        fileUniqueId: "watch-photo-unique",
        height: 400,
        width: 600,
      }],
      replyToMessage: {
        chat: { id: -1007, type: "supergroup" },
        date: 1_699_999_999,
        from: { firstName: "Paritosh", id: 7, isBot: false },
        messageId: 905,
        text: "Can anyone identify this watch?",
      },
    },
    updateId: 906,
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(submitted).toContain("Reply context:");
  expect(submitted).toContain("Can anyone identify this watch?");
  expect(submitted).toContain(Buffer.from(image).toString("base64"));
});

test("ask command records a rejected AI SDK stream as a failure", async () => {
  const send: Fetch = async () => new Response(JSON.stringify({
    error: { code: 401, message: "Invalid OpenRouter key" },
  }), { headers: { "content-type": "application/json" }, status: 401 });
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    await app.run(bot.handler(commandUpdate("/ask hello", 904)));
  } finally {
    await app.close();
  }
  const command = await Effect.runPromise(database.one(
    "SELECT status, error_type, error_message FROM command_stats WHERE message_id = ?",
    [904],
  ));
  database.close();

  expect(command).toMatchObject({
    error_type: "AiError",
    status: "failed",
  });
  expect(command?.["error_message"]).toContain("Invalid OpenRouter key");
  expect(fake.requests.find((request) => request.method === "sendMessage")?.params).toMatchObject({
    text: "Something went wrong. Please try again.",
  });
});

test("ask command stops before OpenRouter after its daily limit", async () => {
  let providerCalls = 0;
  const send: Fetch = async () => {
    providerCalls += 1;
    return openRouterStream("ok");
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

test("edit command uses an image attached to its command caption", async () => {
  const source = new TextEncoder().encode("source-image");
  let submitted = "";
  const send: Fetch = async (_input, init) => {
    submitted = typeof init?.body === "string" ? init.body : "";
    return new Response(JSON.stringify({
      data: [{ b64_json: Buffer.from("generated-image").toString("base64") }],
    }));
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok({
      file_id: "source-photo",
      file_path: "photos/source.jpg",
      file_size: source.length,
      file_unique_id: "source-photo-unique",
    }),
    FakeBotApiReply.file(source),
    sentMessage(98),
  ], aiConfig());
  await allow(database, "edit");
  const update: Update = {
    message: {
      caption: "/edit restore the colors",
      captionEntities: [{ length: 5, offset: 0, type: "bot_command" }],
      chat: { id: -1007, type: "supergroup" },
      date: 1_700_000_000,
      from: { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
      messageId: 907,
      photo: [{
        fileId: "source-photo",
        fileSize: source.length,
        fileUniqueId: "source-photo-unique",
        height: 400,
        width: 600,
      }],
    },
    updateId: 907,
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(submitted).toContain(Buffer.from(source).toString("base64"));
  expect(fake.requests.find((request) => request.method === "sendPhoto")?.params)
    .toMatchObject({ caption: expect.stringContaining("restore the colors") });
});

test("edit command explains an AI SDK moderation rejection", async () => {
  const send: Fetch = async () => new Response(JSON.stringify({
    error: {
      code: "moderation",
      message: "Generated image rejected by content moderation",
    },
  }), { headers: { "content-type": "application/json" }, status: 400 });
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ], aiConfig());
  await allow(database, "edit");

  try {
    await app.run(bot.handler(commandUpdate("/edit unsafe request", 903)));
  } finally {
    await app.close();
    database.close();
  }

  expect(fake.requests.find((request) => request.method === "sendMessage")?.params).toMatchObject({
    text: "The generated image was rejected by content moderation. Try a different prompt or source image.",
  });
});
