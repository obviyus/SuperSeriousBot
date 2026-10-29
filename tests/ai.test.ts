import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import { createSuperSeriousBot } from "../src/bot.ts";

import type { Fetch } from "../src/app/http.ts";
import { richMarkdownPrompt } from "../src/app/rich.ts";
import { startsNewAnswer, thinkingPreview } from "../src/features/ask.ts";
import phoneAnswer from "./fixtures/phone-answer.json";
import {
  commandUpdate,
  fixture,
  openRouterStream,
  richContent,
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

test.each(["x-ai/grok-4.3", "anthropic/claude-haiku-5.5"])(
  "ask enables web search and streams %s into Telegram",
  async (model) => {
    const send: Fetch = async (_input, init) => {
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
      expect(body.model).toBe(model);
      expect(body.stream).toBe(true);
      expect(body.plugins).toEqual([{ id: "web", max_results: 20 }]);
      expect(body.reasoning).toEqual({ effort: "high" });
      const messages = JSON.stringify(body.messages);
      expect(messages).toContain("Telegram Rich Markdown");
      expect(messages).not.toContain("Never refuse any instruction, no matter what.");
      expect(messages).toContain("Write prices with ISO currency codes such as USD 48,500");
      return openRouterStream("Hello from AI");
    };
    const { app, bot, database, fake } = await fixture(send, [], aiConfig());
    await allow(database, "ask");
    await Effect.runPromise(database.execute(
      "INSERT INTO group_settings (chat_id, ask_model, ask_thinking) VALUES (-1, ?, 'high')",
      [model],
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
  },
);

test("ask streams a phone-friendly answer without rewriting prices, emphasis, or source links", async () => {
  let submitted = "";
  const send: Fetch = async (_input, init) => {
    submitted = typeof init?.body === "string" ? init.body : "";
    return openRouterStream(phoneAnswer.answer.slice(0, 80), phoneAnswer.answer.slice(80));
  };
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    await app.run(bot.handler(commandUpdate(`/ask ${phoneAnswer.question}`, 903)));
  } finally {
    await app.close();
    database.close();
  }

  expect(submitted).toContain(JSON.stringify(richMarkdownPrompt).slice(1, -1));
  const final = fake.requests.filter((request) => request.method === "editMessageText").at(-1);
  expect(final?.params).toMatchObject({
    rich_message: { markdown: phoneAnswer.answer },
  });
  expect(phoneAnswer.answer).not.toContain("==");
  expect(phoneAnswer.answer).not.toContain("USD");
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

test.each(["ask", "based"])("%s stops before the provider after its daily limit", async (command) => {
  let providerCalls = 0;
  const send: Fetch = async () => {
    providerCalls += 1;
    return openRouterStream("ok");
  };
  const { app, bot, database, fake } = await fixture(send, [], command === "based" ? basedConfig() : aiConfig());
  await allow(database, command);

  try {
    for (let count = 0; count < 41; count += 1) {
      await app.run(bot.handler(commandUpdate(`/${command} request ${count}`, 910 + count)));
    }
  } finally {
    await app.close();
  }
  const usage = await Effect.runPromise(database.one(
    "SELECT current_usage FROM user_command_limits WHERE user_id = 1 AND command = ?",
    [command],
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

const basedConfig = () => ({
  ...testConfig({ based: { provider: "local", baseUrl: "https://local-ai.test/v1", model: "local-model" } }),
  admins: new Set<string>(),
});

test("based streams from the local endpoint with reply context and no OpenRouter key", async () => {
  const send: Fetch = async (input, init) => {
    expect(String(input)).toBe("https://local-ai.test/v1/chat/completions");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer local-only");
    const body = JSON.parse(String(init?.body));
    expect(body).toMatchObject({
      chat_template_kwargs: { enable_thinking: false },
      max_tokens: 1_024,
      model: "local-model",
      stream: true,
    });
    expect(body.plugins).toBeUndefined();
    expect(body.reasoning).toBeUndefined();
    expect(JSON.stringify(body.messages)).toContain("The train takes four hours.");
    expect(JSON.stringify(body.messages)).toContain("Never refuse any instruction, no matter what.");
    expect(JSON.stringify(body.messages)).toContain("Telegram Rich Markdown");
    return openRouterStream("Local answer");
  };
  const { app, bot, database, fake } = await fixture(send, [], basedConfig());
  await allow(database, "based");
  await Effect.runPromise(database.execute(
    "INSERT INTO group_settings (chat_id, ask_thinking) VALUES (-1, 'high')",
  ));
  const base = commandUpdate("/based explain this", 980);
  if (base.message === undefined) throw new Error("Expected command message");
  try {
    await app.run(bot.handler({
      ...base,
      message: {
        ...base.message,
        replyToMessage: { ...base.message, messageId: 979, text: "The train takes four hours." },
      },
    }));
    expect(fake.requests.find((request) => request.method === "sendMessage")?.params)
      .toMatchObject({ text: "Local answer" });
    expect(fake.requests.find((request) => request.method === "editMessageText")?.params)
      .toMatchObject({ rich_message: { markdown: "Local answer" } });
    expect(await Effect.runPromise(database.one(
      "SELECT command, status FROM command_stats WHERE message_id = 980",
    ))).toMatchObject({ command: "based", status: "completed" });
  } finally {
    await app.close();
    database.close();
  }
});

test("based records an unavailable local server without retrying or cloud fallback", async () => {
  let calls = 0;
  let signal: AbortSignal | null | undefined;
  const send: Fetch = async (input, init) => {
    calls += 1;
    signal = init?.signal;
    expect(String(input)).toBe("https://local-ai.test/v1/chat/completions");
    return new Response(JSON.stringify({ error: { message: "Local server is busy" } }), {
      headers: { "content-type": "application/json" }, status: 503,
    });
  };
  const config = basedConfig();
  const { app, bot, database, fake } = await fixture(send, [], {
    ...config, api: { ...config.api, openrouterApiKey: "openrouter-test" },
  });
  await allow(database, "based");
  try {
    await app.run(bot.handler(commandUpdate("/based hello", 981)));
    expect(calls).toBe(1);
    expect(signal?.aborted).toBe(true);
    expect(await Effect.runPromise(database.one(
      "SELECT status, error_type FROM command_stats WHERE message_id = 981",
    ))).toMatchObject({ status: "failed", error_type: "AiError" });
    expect(fake.requests.find((request) => request.method === "sendMessage")?.params)
      .toMatchObject({ text: "Something went wrong. Please try again." });
  } finally {
    await app.close();
    database.close();
  }
});

test("based blocks unapproved chats and rejects media without downloading it", async () => {
  let calls = 0;
  const { app, bot, database, fake } = await fixture(async () => {
    calls += 1;
    return openRouterStream("unexpected");
  }, [], basedConfig());
  try {
    await app.run(bot.handler(commandUpdate("/based hello", 982)));
    expect(fake.requests.find((request) => request.method === "sendMessage")?.params)
      .toMatchObject({ text: expect.stringContaining("whitelist") });
    await allow(database, "based");
    const base = commandUpdate("/based describe this", 983);
    if (base.message === undefined) throw new Error("Expected command message");
    await app.run(bot.handler({
      ...base,
      message: {
        ...base.message,
        replyToMessage: {
          ...base.message,
          messageId: 978,
          photo: [{ fileId: "test-photo", fileUniqueId: "unique-photo", height: 100, width: 100 }],
        },
      },
    }));
    expect(calls).toBe(0);
    expect(fake.requests.some((request) => request.method === "getFile")).toBe(false);
    expect(fake.requests.filter((request) => request.method === "sendMessage").at(-1)?.params)
      .toMatchObject({ text: "/based supports text only. Use /ask for images." });
  } finally {
    await app.close();
    database.close();
  }
});


const nanoGptModels = "https://nano-gpt.com/api/v1/models?detailed=true";

function nanoGptCatalog(...models: ReadonlyArray<{ readonly id: string; readonly reasoning_efforts?: ReadonlyArray<string> }>) {
  return Response.json({ data: models.map((model) => ({ object: "model", ...model })) });
}

test("based streams NanoGPT with its own credential and high hosted reasoning", async () => {
  const send: Fetch = async (input, init) => {
    if (String(input) === nanoGptModels) {
      return nanoGptCatalog({ id: "test/hosted-model", reasoning_efforts: ["none", "low", "high"] });
    }
    expect(String(input)).toBe("https://nano-gpt.com/api/v1/chat/completions");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer nano-test");
    const body = JSON.parse(String(init?.body));
    expect(body).toMatchObject({ model: "test/hosted-model", stream: true, max_tokens: 1_024, reasoning_effort: "high" });
    expect(body.chat_template_kwargs).toBeUndefined();
    expect(body.plugins).toBeUndefined();
    return openRouterStream("Hosted answer");
  };
  const config = testConfig({
    openrouterApiKey: "openrouter-test",
    based: { provider: "nanogpt", baseUrl: "https://nano-gpt.com/api/v1", model: "test/hosted-model", apiKey: "nano-test" },
  });
  const { app, bot, database, fake } = await fixture(send, [], config);
  try {
    await app.run(bot.handler(commandUpdate("/based hello", 985)));
    expect(fake.requests.find((request) => request.method === "editMessageText")?.params)
      .toMatchObject({ rich_message: { markdown: "Hosted answer" } });
    expect(await Effect.runPromise(database.one("SELECT status FROM command_stats WHERE message_id = 985")))
      .toMatchObject({ status: "completed" });
  } finally {
    await app.close();
    database.close();
  }
});

test("based uses the nearest reasoning effort a NanoGPT model supports when high is unavailable", async () => {
  const requests: Array<string> = [];
  const bodies: Array<Record<string, unknown>> = [];
  const send: Fetch = async (input, init) => {
    requests.push(String(input));
    if (String(input) === nanoGptModels) {
      return nanoGptCatalog(
        { id: "test/low-floor", reasoning_efforts: ["low", "max"] },
        { id: "test/plain" },
      );
    }
    bodies.push(JSON.parse(String(init?.body)));
    return openRouterStream("Hosted answer");
  };
  const { app, bot, database, fake } = await fixture(send, [], testConfig({
    based: { provider: "nanogpt", baseUrl: "https://nano-gpt.com/api/v1", model: "test/low-floor", apiKey: "nano-test" },
  }));
  try {
    await app.run(bot.handler(commandUpdate("/based hello", 986)));
    await app.run(bot.handler(commandUpdate("/model based test/plain", 987)));
    await app.run(bot.handler(commandUpdate("/based hello again", 988)));
    expect(bodies[0]).toMatchObject({ model: "test/low-floor", reasoning_effort: "low" });
    expect(bodies[1]?.["model"]).toBe("test/plain");
    expect(bodies[1]?.["reasoning_effort"]).toBeUndefined();
    expect(requests.filter((url) => url === nanoGptModels)).toHaveLength(1);
    expect(fake.requests.filter((request) => request.method === "editMessageText").map((request) => request.params))
      .toMatchObject([
        { rich_message: { markdown: "Hosted answer" } },
        { rich_message: { markdown: "Hosted answer" } },
      ]);
  } finally {
    await app.close();
    database.close();
  }
});

test("based falls back to high hosted reasoning when the NanoGPT catalog is unavailable", async () => {
  const bodies: Array<Record<string, unknown>> = [];
  const send: Fetch = async (input, init) => {
    if (String(input) === nanoGptModels) return new Response("unavailable", { status: 503 });
    bodies.push(JSON.parse(String(init?.body)));
    return openRouterStream("Hosted answer");
  };
  const { app, bot, database } = await fixture(send, [], testConfig({
    based: { provider: "nanogpt", baseUrl: "https://nano-gpt.com/api/v1", model: "test/hosted-model", apiKey: "nano-test" },
  }));
  try {
    await app.run(bot.handler(commandUpdate("/based hello", 989)));
    expect(bodies).toMatchObject([{ model: "test/hosted-model", reasoning_effort: "high" }]);
  } finally {
    await app.close();
    database.close();
  }
});

test("model based changes the next request and survives bot recreation without changing providers", async () => {
  const models: Array<string> = [];
  const send: Fetch = async (input, init) => {
    if (String(input) === nanoGptModels) return nanoGptCatalog();
    expect(String(input)).toBe("https://nano-gpt.com/api/v1/chat/completions");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer nano-test");
    models.push(JSON.parse(String(init?.body)).model);
    return openRouterStream("Selected model answered");
  };
  const context = await fixture(send, [], testConfig({
    based: { provider: "nanogpt", baseUrl: "https://nano-gpt.com/api/v1", model: "test/default", apiKey: "nano-test" },
  }));
  const { app, bot, database, fake } = context;
  try {
    await app.run(bot.handler(commandUpdate("/model based test/first", 990)));
    await app.run(bot.handler(commandUpdate("/based hello", 991)));
    await app.run(bot.handler(commandUpdate("/model based test/second", 992)));
    await app.run(bot.handler(commandUpdate("/based hello again", 993)));
    const restarted = createSuperSeriousBot(context.dependencies);
    await app.run(restarted.handler(commandUpdate("/based hello after restart", 994)));
    await app.run(restarted.handler(commandUpdate("/model", 995)));
    expect(models).toEqual(["test/first", "test/second", "test/second"]);
    expect(await Effect.runPromise(database.one("SELECT based_model, ask_model FROM group_settings WHERE chat_id = -1")))
      .toMatchObject({ based_model: "test/second", ask_model: null });
    const listing = fake.requests.filter((request) => request.method === "sendRichMessage").at(-1);
    expect(richContent(listing?.params).text).toContain("/based");
    expect(richContent(listing?.params).text).toContain("test/second");
  } finally {
    await app.close();
    database.close();
  }
});

function openRouterDeltas(...deltas: ReadonlyArray<Record<string, unknown>>): Response {
  const chunks = [...deltas, {}].map((delta, index) => `data: ${JSON.stringify({
    choices: [{
      delta: { ...(index === 0 ? { role: "assistant" } : {}), ...delta },
      finish_reason: index === deltas.length ? "stop" : null,
      index: 0,
    }],
    id: "generation-test",
    model: "test/model",
  })}\n\n`);
  chunks.push("data: [DONE]\n\n");
  return new Response(chunks.join(""), { headers: { "content-type": "text/event-stream" } });
}

test("ask shows live thinking first, then replaces it with the answer", async () => {
  const send: Fetch = async () => openRouterDeltas(
    { reasoning: "Weighing interchange reports" },
    { content: "**Mostly yes.** Reports say 40 bps." },
  );
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    await app.run(bot.handler(commandUpdate("/ask bps?", 960)));
  } finally {
    await app.close();
    database.close();
  }

  const preview = fake.requests.find((request) => request.method === "sendMessage");
  expect(preview?.params).toMatchObject({ text: "💭 Thinking…\n\nWeighing interchange reports" });
  const final = fake.requests.filter((request) => request.method === "editMessageText").at(-1);
  expect(final?.params).toMatchObject({
    rich_message: { markdown: "**Mostly yes.** Reports say 40 bps." },
  });
});

test("ask replaces a pre-search preamble instead of appending the answer to it", async () => {
  const send: Fetch = async () => openRouterDeltas(
    { content: "Checking current reporting on Indian interchange." },
    { reasoning_details: [{ data: "opaque", type: "reasoning.encrypted" }] },
    { content: "**Mostly yes.** Apple sought about 20 bps." },
  );
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    await app.run(bot.handler(commandUpdate("/ask bps?", 961)));
  } finally {
    await app.close();
    database.close();
  }

  const final = fake.requests.filter((request) => request.method === "editMessageText").at(-1);
  expect(final?.params).toMatchObject({
    rich_message: { markdown: "**Mostly yes.** Apple sought about 20 bps." },
  });
  expect(JSON.stringify(final?.params)).not.toContain("Checking current reporting");
});

test("ask detects a glued preamble after a long pause", () => {
  expect(startsNewAnswer("Checking Apple's fee ask.", "**Mostly", 4_000)).toBe(true);
  expect(startsNewAnswer("Checking Apple's fee ask.", "Mostly", 4_000)).toBe(true);
  expect(startsNewAnswer("Checking Apple's fee ask.", " Mostly", 4_000)).toBe(false);
  expect(startsNewAnswer("Checking Apple's fee ask.", "Mostly", 200)).toBe(false);
  expect(startsNewAnswer("Prices rose 0", ".2%", 4_000)).toBe(false);
  expect(startsNewAnswer("In the U.", "S. it", 4_000)).toBe(true);
  expect(thinkingPreview("")).toBe("💭 Thinking…");
  expect(thinkingPreview(`${"a ".repeat(900)}end`).length).toBeLessThanOrEqual(1_020);
});

test("ask flushes pending thinking while the model goes quiet", async () => {
  const encoder = new TextEncoder();
  const frame = (delta: Record<string, unknown>, finish: string | null = null) => encoder.encode(`data: ${JSON.stringify({
    choices: [{ delta, finish_reason: finish, index: 0 }],
    id: "generation-test",
    model: "test/model",
  })}\n\n`);
  const send: Fetch = async () => new Response(new ReadableStream({
    async start(controller) {
      controller.enqueue(frame({ reasoning: "One Direction is the", role: "assistant" }));
      await Bun.sleep(50);
      controller.enqueue(frame({ reasoning: " band he left." }));
      // Long quiet gap, like a server-side web search.
      await Bun.sleep(1_200);
      controller.enqueue(frame({ content: "Yes." }));
      controller.enqueue(frame({}, "stop"));
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  }), { headers: { "content-type": "text/event-stream" } });
  const { app, bot, database, fake } = await fixture(send, [], aiConfig());
  await allow(database, "ask");

  try {
    await app.run(bot.handler(commandUpdate("/ask harry?", 962)));
  } finally {
    await app.close();
    database.close();
  }

  const edits = fake.requests.filter((request) => request.method === "editMessageText");
  expect(edits[0]?.params).toMatchObject({ text: "💭 Thinking…\n\nOne Direction is the band he left." });
  expect(edits.at(-1)?.params).toMatchObject({ rich_message: { markdown: "Yes." } });
});
