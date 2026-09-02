import { expect, test } from "bun:test";
import { type Update } from "telly";

import type { Fetch } from "../src/app/http.ts";
import { fixture } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

test("good bot text receives one deterministic positive reaction", async () => {
  const { app, bot, database, fake } = await fixture(offline);
  const update: Update = {
    message: {
      chat: { id: -1007, type: "supergroup" },
      date: 1_700_000_000,
      from: { firstName: "Alice", id: 2, isBot: false },
      messageId: 6_001,
      text: "That was a good bot response",
    },
    updateId: 6_001,
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(fake.requests.find((request) => request.method === "setMessageReaction")?.params).toMatchObject({
    chat_id: -1007,
    message_id: 6_001,
    reaction: [{ emoji: "💋", type: "emoji" }],
  });
});

test("sed correction replies with the corrected source text", async () => {
  const { app, bot, database, fake } = await fixture(offline);
  const update: Update = {
    message: {
      chat: { id: -1007, type: "supergroup" },
      date: 1_700_000_001,
      from: { firstName: "Alice", id: 2, isBot: false },
      messageId: 6_003,
      replyToMessage: {
        chat: { id: -1007, type: "supergroup" },
        date: 1_700_000_000,
        from: { firstName: "Ayaan", id: 1, isBot: false },
        messageId: 6_002,
        text: "This framework is wrong",
      },
      text: "s/wrong/beautiful",
    },
    updateId: 6_003,
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(fake.requests.find((request) => request.method === "sendMessage")?.params).toMatchObject({
    chat_id: -1007,
    reply_parameters: { message_id: 6_002 },
    text: "This framework is beautiful",
  });
});
