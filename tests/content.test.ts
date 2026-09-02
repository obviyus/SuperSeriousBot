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

test("tldr fetches and caches a fresh YouTube transcript summary", async () => {
  const send: Fetch = async (input) => String(input).includes("youtube-transcribe")
    ? new Response(JSON.stringify({ transcripts: [{ transcript: "A detailed camera review." }] }))
    : new Response(JSON.stringify({
        choices: [{ message: { content: "- The camera is compact.\n- Stabilization is excellent." } }],
      }));
  const config = {
    ...testConfig({ nanoGptApiKey: "nano-test", openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database, fake } = await fixture(send, [], config);
  await Effect.runPromise(database.execute(
    "INSERT INTO command_whitelist (command, whitelist_type, whitelist_id) VALUES ('tldr', 'chat', ?)",
    [-1007],
  ));
  const base = commandUpdate("/tldr https://youtu.be/fresh123", 1_002);
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
  }
  const cached = await Effect.runPromise(database.one(
    "SELECT summary, user_id FROM tldw WHERE video_id = ?",
    ["fresh123"],
  ));
  database.close();

  expect(cached).toMatchObject({
    summary: "- The camera is compact.\n- Stabilization is excellent.",
    user_id: 1,
  });
  const reply = fake.requests.filter((request) => request.method === "sendMessage").at(-1);
  expect(reply?.params).toMatchObject({ text: expect.stringContaining("Stabilization is excellent") });
});

function silentWav(): Uint8Array {
  const sampleCount = 1_600;
  const bytes = new Uint8Array(44 + sampleCount * 2);
  const view = new DataView(bytes.buffer);
  const label = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) bytes[offset + index] = value.charCodeAt(index);
  };
  label(0, "RIFF");
  view.setUint32(4, bytes.length - 8, true);
  label(8, "WAVE");
  label(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16_000, true);
  view.setUint32(28, 32_000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  label(36, "data");
  view.setUint32(40, sampleCount * 2, true);
  return bytes;
}

test("tr command downloads audio, transcodes it, and sends the transcript", async () => {
  let audioInput = "";
  const send: Fetch = async (_input, init) => {
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    audioInput = body.messages?.[0]?.content?.[1]?.input_audio?.data ?? "";
    return new Response(JSON.stringify({
      choices: [{ message: { content: "The speaker asks for a camera recommendation." } }],
    }));
  };
  const source = silentWav();
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok({
      file_id: "voice-file",
      file_path: "voice/source.ogg",
      file_size: source.length,
      file_unique_id: "voice-unique",
    }),
    FakeBotApiReply.file(source),
  ], config);
  await Effect.runPromise(database.execute(
    "INSERT INTO command_whitelist (command, whitelist_type, whitelist_id) VALUES ('tr', 'chat', ?)",
    [-1007],
  ));
  const base = commandUpdate("/tr", 1_003);
  if (base.message === undefined) throw new Error("Expected command message");
  const update: Update = {
    ...base,
    message: {
      ...base.message,
      replyToMessage: {
        chat: base.message.chat,
        date: base.message.date - 1,
        messageId: 1_002,
        voice: {
          duration: 1,
          fileId: "voice-file",
          fileSize: source.length,
          fileUniqueId: "voice-unique",
          mimeType: "audio/ogg",
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

  expect(Buffer.from(audioInput, "base64").subarray(0, 4).toString()).toBe("RIFF");
  const reply = fake.requests.filter((request) => request.method === "sendMessage").at(-1);
  expect(reply?.params).toMatchObject({
    text: expect.stringContaining("camera recommendation"),
  });
});
