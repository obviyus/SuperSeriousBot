import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

function callbackDataFrom(request: unknown, label: string): string {
  if (typeof request !== "object" || request === null) throw new Error(`${label} request missing`);
  const markup = Reflect.get(request, "reply_markup");
  if (typeof markup !== "object" || markup === null) throw new Error(`${label} keyboard missing`);
  const rows = Reflect.get(markup, "inline_keyboard");
  if (!Array.isArray(rows)) throw new Error(`${label} rows missing`);
  for (const row of rows) {
    if (!Array.isArray(row)) continue;
    for (const button of row) {
      if (typeof button !== "object" || button === null) continue;
      const data = Reflect.get(button, "callback_data");
      if (typeof data === "string" && Reflect.get(button, "text") === label) return data;
    }
  }
  throw new Error(`${label} button missing`);
}

function callback(
  updateId: number,
  data: string,
  messageId: number,
  from = { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
): Update {
  return {
    callbackQuery: {
      chatInstance: "social-chat",
      data,
      from,
      id: `callback-${updateId}`,
      message: {
        chat: { id: -1007, title: "Telly Lab", type: "supergroup" },
        date: 1_700_000_001,
        messageId,
      },
    },
    updateId,
  };
}

test("summon creates a group and its Join button adds another member", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok({
      status: "member",
      user: { first_name: "Ayaan", id: 1, is_bot: false, username: "obviyus" },
    }),
  ]);

  try {
    await app.run(bot.handler(commandUpdate("/summon players", 701)));
    const summon = fake.requests.find((request) => request.method === "sendMessage");
    const joinData = callbackDataFrom(summon?.params, "✅ Join");
    const join = callback(702, joinData, 92, {
      firstName: "Alice",
      id: 2,
      isBot: false,
      username: "alice",
    });
    await app.run(bot.handler(join));
  } finally {
    await app.close();
  }
  const members = await Effect.runPromise(database.all(
    "SELECT user_id FROM summon_group_members ORDER BY user_id",
  ));
  database.close();

  expect(members.map((row) => row["user_id"])).toEqual([1, 2]);
});

test("habit Check-in button records one daily completion", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
  ]);

  try {
    await app.run(bot.handler(commandUpdate("/habit workout 5", 703)));
    const messages = fake.requests.filter((request) => request.method === "sendMessage");
    const checkinData = callbackDataFrom(messages.at(-1)?.params, "📅 Check-in");
    fake.enqueue(FakeBotApiReply.ok(true));
    fake.enqueue(FakeBotApiReply.ok(true));
    await app.run(bot.handler(callback(704, checkinData, 93)));
  } finally {
    await app.close();
  }
  const logs = await Effect.runPromise(database.all(
    "SELECT user_id FROM habit_log",
  ));
  database.close();

  expect(logs.map((row) => row["user_id"])).toEqual([1]);
  const answer = fake.requests.find((request) => request.method === "answerCallbackQuery");
  expect(answer?.params).toMatchObject({ text: "Checked in successfully!" });
});

test("highlight sends a private alert when tracked text appears", async () => {
  const { app, bot, database, fake } = await fixture(offline, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok({
      first_name: "Super Serious",
      id: 123456,
      is_bot: true,
      username: "SuperSeriousBot",
    }),
  ]);
  const mention: Update = {
    message: {
      chat: { id: -1007, title: "Telly Lab", type: "supergroup", username: "tellylab" },
      date: 1_700_000_002,
      from: { firstName: "Alice", id: 2, isBot: false, username: "alice" },
      messageId: 95,
      text: "Elden Ring is tonight",
    },
    updateId: 705,
  };

  try {
    await app.run(bot.handler(commandUpdate("/highlight Elden Ring", 705)));
    await app.run(bot.handler(mention));
  } finally {
    await app.close();
    database.close();
  }

  const direct = fake.requests.filter((request) => request.method === "sendMessage").at(-1);
  expect(direct?.params).toMatchObject({
    chat_id: 1,
    text: expect.stringContaining("Elden Ring"),
  });
});

test("unknown legacy callback data receives an expired-button answer", async () => {
  const { app, bot, database, fake } = await fixture(offline);

  try {
    await app.run(bot.handler(callback(706, "hb:checkin,1", 96)));
  } finally {
    await app.close();
    database.close();
  }

  const answer = fake.requests.find((request) => request.method === "answerCallbackQuery");
  expect(answer?.params).toMatchObject({ text: "This button expired." });
});
