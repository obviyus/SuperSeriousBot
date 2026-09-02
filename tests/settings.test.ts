import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, richContent } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");
const presence = () => [FakeBotApiReply.ok(true), FakeBotApiReply.ok(true)] as const;

test("model command updates every AI model in one database write", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate("/model all openrouter/test/model", 601)));
  } finally {
    await app.close();
  }
  const row = await Effect.runPromise(database.one(
    `SELECT ask_model, cron_model, edit_model, search_model,
            song_model, tr_model, tldr_model, video_model
     FROM group_settings WHERE chat_id = -1`,
  ));
  database.close();

  expect(row?.["ask_model"]).toBe("openrouter/test/model");
  expect(row?.["cron_model"]).toBe("openrouter/test/model");
  expect(row?.["edit_model"]).toBe("openrouter/test/model");
  expect(row?.["search_model"]).toBe("openrouter/test/model");
  expect(row?.["song_model"]).toBe("openrouter/test/model");
  expect(row?.["tr_model"]).toBe("openrouter/test/model");
  expect(row?.["tldr_model"]).toBe("openrouter/test/model");
  expect(row?.["video_model"]).toBe("openrouter/test/model");
  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: expect.stringContaining("All command models") });
});

test("model command configures video generation", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate(
      "/model video openrouter/bytedance/seedance-test",
      605,
    )));
  } finally {
    await app.close();
  }
  const row = await Effect.runPromise(database.one(
    "SELECT video_model FROM group_settings WHERE chat_id = -1",
  ));
  database.close();

  expect(row?.["video_model"]).toBe("openrouter/bytedance/seedance-test");
  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: expect.stringContaining("Model for <b>/video</b>") });
});

test("model command presents configured models in a native rich table", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate("/model", 604)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("/ask");
  expect(content.text).toContain("openrouter/x-ai/grok-4.3");
  expect(content.types).toContain("table");
});

test("settings callback toggles message search and redraws the keyboard", async () => {
  const { app, bot, database, fake } = await fixture(offline, presence());

  try {
    await app.run(bot.handler(commandUpdate("/settings", 602)));
    const sent = fake.requests.find((request) => request.method === "sendRichMessage");
    if (typeof sent?.params !== "object" || sent.params === null) {
      throw new Error("Settings command sent no parameters");
    }
    const markup = Reflect.get(sent.params, "reply_markup");
    if (typeof markup !== "object" || markup === null) throw new Error("Settings has no keyboard");
    const rows = Reflect.get(markup, "inline_keyboard");
    const firstRow = Array.isArray(rows) ? rows[0] : undefined;
    const button = Array.isArray(firstRow) ? firstRow[0] : undefined;
    const data = typeof button === "object" && button !== null
      ? Reflect.get(button, "callback_data")
      : undefined;
    if (typeof data !== "string") throw new Error("Settings button has no callback data");
    fake.enqueue(FakeBotApiReply.ok(true));
    fake.enqueue(FakeBotApiReply.ok(true));
    const callback: Update = {
      callbackQuery: {
        chatInstance: "settings-chat",
        data,
        from: { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
        id: "settings-callback",
        message: {
          chat: { id: -1007, title: "Telly Lab", type: "supergroup" },
          date: 1_700_000_001,
          messageId: 91,
        },
      },
      updateId: 603,
    };
    await app.run(bot.handler(callback));
  } finally {
    await app.close();
  }
  const row = await Effect.runPromise(database.one(
    "SELECT fts FROM group_settings WHERE chat_id = ?",
    [-1007],
  ));
  database.close();

  expect(row?.["fts"]).toBe(1);
  const edit = fake.requests.find((request) => request.method === "editMessageText");
  if (typeof edit?.params !== "object" || edit.params === null) {
    throw new Error("Settings callback did not edit its message");
  }
  const markup = Reflect.get(edit.params, "reply_markup");
  const rows = typeof markup === "object" && markup !== null
    ? Reflect.get(markup, "inline_keyboard")
    : undefined;
  const firstRow = Array.isArray(rows) ? rows[0] : undefined;
  const firstButton = Array.isArray(firstRow) ? firstRow[0] : undefined;
  const firstText = typeof firstButton === "object" && firstButton !== null
    ? Reflect.get(firstButton, "text")
    : undefined;
  expect(Reflect.get(edit.params, "chat_id")).toBe(-1007);
  expect(Reflect.get(edit.params, "message_id")).toBe(91);
  expect(firstText).toBe("On - Message search");
  expect(richContent(edit.params).text).toContain("Group settings");
});
