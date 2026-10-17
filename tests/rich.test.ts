import { expect, test } from "bun:test";
import { Application, BotApiError } from "telly";
import { FakeBotApi, FakeBotApiReply } from "telly/testing";

import { replyBlocks, replyRich, rich, richMarkdownPrompt, richMessageLimit } from "../src/app/rich.ts";
import { commandUpdate, sentMessage, token } from "./harness.ts";

test("AI formatting policy favors readable phone answers without decorative highlighting", () => {
  expect(richMarkdownPrompt).toContain("narrow phone screen");
  expect(richMarkdownPrompt).toContain("Lead with the direct answer or recommendation");
  expect(richMarkdownPrompt).toContain("one idea per bullet");
  expect(richMarkdownPrompt).toContain("Use **bold** sparingly");
  expect(richMarkdownPrompt).toContain("Do not use ==highlight== unless the user explicitly requests highlighting");
  expect(richMarkdownPrompt).toContain("preserve requested depth");
  expect(richMarkdownPrompt).toContain("prefer labeled bullets");
  expect(richMarkdownPrompt).toContain("Do not add currency conversions unless asked");
  expect(richMarkdownPrompt).toContain("links next to the claims they support");
  expect(richMarkdownPrompt).toContain("do not invent sources");
  expect(richMarkdownPrompt).toContain("Use $...$ only for intentional mathematical expressions");
});

function sourceMessage() {
  const message = commandUpdate("/ask format this", 8_001).message;
  if (message === undefined) throw new Error("Expected source message");
  return message;
}

test("rich reply falls back to plain text after a known Telegram rejection", async () => {
  const fake = FakeBotApi.make({
    replies: [FakeBotApiReply.reject({
      description: "Bad Request: can't parse rich message",
      errorCode: 400,
    })],
    token,
  });
  const app = Application.make({ httpClient: fake.layer, rateLimit: false, token });

  try {
    await app.run(replyRich(sourceMessage(), "## Useful answer"));
  } finally {
    await app.close();
  }

  expect(fake.requests.map(({ method }) => method)).toEqual([
    "sendRichMessage",
    "sendMessage",
  ]);
  expect(fake.requests.at(-1)?.params).toMatchObject({ text: "## Useful answer" });
});

test("rich reply does not risk a duplicate after an unknown transport outcome", async () => {
  const fake = FakeBotApi.make({
    replies: [FakeBotApiReply.transportFailure("connection reset after write")],
    token,
  });
  const app = Application.make({ httpClient: fake.layer, rateLimit: false, token });

  try {
    await expect(app.run(replyRich(sourceMessage(), "## Possibly delivered")))
      .rejects.toBeInstanceOf(BotApiError);
  } finally {
    await app.close();
  }

  expect(fake.requests.map(({ method }) => method)).toEqual(["sendRichMessage"]);
});

test("rich reply sends text beyond Telegram's rich limit as a document", async () => {
  const fake = FakeBotApi.make({ replies: [sentMessage(8_002)], token });
  const app = Application.make({ httpClient: fake.layer, rateLimit: false, token });
  const text = "x".repeat(richMessageLimit + 1);

  try {
    await app.run(replyRich(sourceMessage(), text, { documentName: "long-answer.txt" }));
  } finally {
    await app.close();
  }

  expect(fake.requests).toHaveLength(1);
  expect(fake.requests[0]).toMatchObject({
    contentType: "multipart/form-data",
    method: "sendDocument",
  });
  expect(Object.values(fake.requests[0]?.files ?? {})[0]).toMatchObject({
    fileName: "long-answer.txt",
    size: richMessageLimit + 1,
  });
});

test("rich blocks preserve group replies, private responses, and keyboards", async () => {
  const fake = FakeBotApi.make({ token });
  const app = Application.make({ httpClient: fake.layer, rateLimit: false, token });
  const group = sourceMessage();
  const direct = { ...group, chat: { id: 77, type: "private" as const } };
  const replyMarkup = { inlineKeyboard: [[{ callbackData: "open", text: "Open" }]] };

  try {
    await app.run(replyBlocks(group, [rich.heading("Group result")], { replyMarkup }));
    await app.run(replyBlocks(direct, [rich.heading("Private result")]));
  } finally {
    await app.close();
  }

  expect(fake.requests[0]?.params).toMatchObject({
    reply_markup: { inline_keyboard: [[{ callback_data: "open", text: "Open" }]] },
    reply_parameters: { message_id: group.messageId },
    rich_message: { blocks: [{ text: "Group result", type: "heading" }] },
  });
  expect(fake.requests[1]?.params).not.toHaveProperty("reply_parameters");
});
