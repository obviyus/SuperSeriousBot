import { expect, test } from "bun:test";
import { Application, BotApiError } from "telly";
import { FakeBotApi, FakeBotApiReply } from "telly/testing";

import { replyRich, richMessageLimit } from "../src/app/rich.ts";
import { commandUpdate, sentMessage, token } from "./harness.ts";

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
