import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, sentMessage, testConfig } from "./harness.ts";

function urlUpdate(text: string, updateId: number): Update {
  const base = commandUpdate(text, updateId);
  if (base.message === undefined) throw new Error("Expected message");
  const offset = text.indexOf("https://");
  const entities = text.startsWith("/")
    ? [
        { length: text.indexOf(" "), offset: 0, type: "bot_command" as const },
        { length: text.length - offset, offset, type: "url" as const },
      ]
    : [{ length: text.length - offset, offset, type: "url" as const }];
  return {
    ...base,
    message: {
      ...base.message,
      entities,
    },
  };
}

test("dl command downloads a Cobalt image and sends it as a photo", async () => {
  const send: Fetch = async (input) => String(input).startsWith("https://cobalt.test")
    ? new Response(JSON.stringify({
        filename: "receipt.jpg",
        status: "tunnel",
        url: "https://media.test/receipt.jpg",
      }))
    : new Response("photo-bytes", { headers: { "content-type": "image/jpeg" } });
  const config = testConfig({ cobaltUrl: "https://cobalt.test" });
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(301),
  ], config);

  try {
    await app.run(bot.handler(urlUpdate("/dl https://example.test/photo", 3_001)));
  } finally {
    await app.close();
    database.close();
  }

  const photo = fake.requests.find((request) => request.method === "sendPhoto");
  expect(photo?.contentType).toBe("multipart/form-data");
  expect(Object.values(photo?.files ?? {})[0]?.fileName).toBe("receipt.jpg");
  expect(Object.values(photo?.files ?? {})[0]?.size).toBe(11);
});

test("automatic download reacts and downloads an Instagram reel when enabled", async () => {
  const send: Fetch = async (input) => String(input).startsWith("https://cobalt.test")
    ? new Response(JSON.stringify({
        filename: "reel.mp4",
        status: "redirect",
        url: "https://media.test/reel.mp4",
      }))
    : new Response("video-bytes", { headers: { "content-type": "video/mp4" } });
  const config = testConfig({ cobaltUrl: "https://cobalt.test" });
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    sentMessage(302),
  ], config);
  await Effect.runPromise(database.execute(
    "INSERT INTO group_settings (chat_id, auto_dl) VALUES (?, 1)",
    [-1007],
  ));
  const update = urlUpdate("look https://www.instagram.com/reel/ABC123/", 3_002);

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(fake.requests.some((request) => request.method === "setMessageReaction")).toBe(true);
  expect(fake.requests.find((request) => request.method === "sendVideo")?.params).toMatchObject({
    chat_id: "-1007",
  });
});
