import { createClient } from "@libsql/client";
import { Predicate } from "effect";
import { Application, Effect, type Update } from "telly";
import { FakeBotApi, FakeBotApiReply } from "telly/testing";

import type { ApiConfig, AppConfig } from "../src/app/config.ts";
import { Database } from "../src/app/database.ts";
import type { AppDependencies } from "../src/app/dependencies.ts";
import { Http, type Fetch } from "../src/app/http.ts";
import { initializeDatabase } from "../src/app/schema.ts";
import { createSuperSeriousBot } from "../src/bot.ts";

export const token = "123456:bot-test";

export function testConfig(api: ApiConfig = {}): AppConfig {
  return {
    admins: new Set(["1"]),
    api,
    port: 8_443,
    quoteChannelId: -1001,
    stateDirectory: "./db",
    telegramToken: token,
    tursoAuthToken: "test",
    tursoDatabaseUrl: ":memory:",
    updater: "polling",
  };
}

export function commandUpdate(text: string, updateId: number): Update {
  const command = text.split(" ", 1)[0] ?? text;
  return {
    message: {
      chat: { id: -1007, type: "supergroup" },
      date: 1_700_000_000,
      entities: [{ length: command.length, offset: 0, type: "bot_command" }],
      from: { firstName: "Ayaan", id: 1, isBot: false, username: "obviyus" },
      messageId: updateId,
      text,
    },
    updateId,
  };
}

export function sentMessage(messageId: number) {
  return FakeBotApiReply.ok({
    chat: { id: -1007, type: "supergroup" },
    date: 1_700_000_001,
    message_id: messageId,
  });
}

export function openRouterText(content: string): Response {
  return new Response(JSON.stringify({
    choices: [{
      finish_reason: "stop",
      index: 0,
      message: { content, role: "assistant" },
    }],
    id: "generation-test",
    model: "test/model",
    provider: "test",
  }), { headers: { "content-type": "application/json" } });
}

export function openRouterStream(...content: ReadonlyArray<string>): Response {
  const chunks = content.map((text, index) => `data: ${JSON.stringify({
    choices: [{
      delta: { ...(index === 0 ? { role: "assistant" } : {}), content: text },
      finish_reason: null,
      index: 0,
    }],
    id: "generation-test",
    model: "test/model",
  })}\n\n`);
  chunks.push(`data: ${JSON.stringify({
    choices: [{ delta: {}, finish_reason: "stop", index: 0 }],
    id: "generation-test",
    model: "test/model",
  })}\n\n`, "data: [DONE]\n\n");
  return new Response(chunks.join(""), { headers: { "content-type": "text/event-stream" } });
}

export function openRouterEmbeddings(requestBody: string): Response {
  const request = JSON.parse(requestBody) as {
    readonly dimensions: number;
    readonly input: ReadonlyArray<string>;
  };
  return new Response(JSON.stringify({
    data: request.input.map((_, index) => ({
      embedding: Array(request.dimensions).fill(0.01),
      index,
      object: "embedding",
    })),
    model: "qwen/qwen3-embedding-8b",
    object: "list",
  }), { headers: { "content-type": "application/json" } });
}

export function richContent(params: unknown): {
  readonly text: string;
  readonly types: ReadonlyArray<string>;
} {
  const types: Array<string> = [];
  const read = (value: unknown): ReadonlyArray<string> => {
    if (typeof value === "string") return [value];
    if (Array.isArray(value)) return value.flatMap(read);
    if (!Predicate.isObject(value)) return [];
    if (typeof value["type"] === "string") types.push(value["type"]);
    return ["text", "summary", "blocks", "items", "cells"].flatMap((key) => read(value[key]));
  };
  const richMessage = Predicate.isObject(params) ? params["rich_message"] : undefined;
  return { text: read(richMessage).join("\n"), types };
}

export async function fixture(
  send: Fetch,
  replies: ReadonlyArray<FakeBotApiReply> = [],
  config: AppConfig = testConfig(),
) {
  const database = new Database(createClient({ intMode: "number", url: "file::memory:" }));
  await Effect.runPromise(initializeDatabase(database));
  const dependencies: AppDependencies = {
    config,
    database,
    http: new Http(send),
    monotonicMilliseconds: performance.now.bind(performance),
    now: () => new Date("2026-09-01T12:00:00Z"),
    random: () => 0.5,
  };
  const fake = FakeBotApi.make({ replies, token });
  const app = Application.make({ httpClient: fake.layer, rateLimit: false, token });
  return { app, bot: createSuperSeriousBot(dependencies), database, fake };
}
