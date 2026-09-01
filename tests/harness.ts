import { createClient } from "@libsql/client";
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
