import { EventEmitter } from "node:events";

import { expect, test } from "bun:test";
import { Fiber, Layer, Redacted } from "effect";
import { TestClock } from "effect/testing";
import { Application, Bot, Effect, InboxStore, MemoryInbox, MemoryJobs, pollInboxUpdates } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { Http } from "../src/app/http.ts";
import {
  runtimeJobs,
  scheduleRuntimeJobs,
  waitForWebhook,
} from "../src/runtime.ts";
import { commandUpdate, fixture, richContent, testConfig, token } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

test("bundled Telly keeps durable polling alive through a Telegram outage", async () => {
  const fault = FakeBotApiReply.reject({ description: "Bad Gateway", errorCode: 502 });
  const { app, bot, database, fake } = await fixture(offline, [
    ...Array.from({ length: 6 }, () => fault),
    FakeBotApiReply.ok([{
      update_id: 9_001,
      message: {
        message_id: 9_001,
        date: 1_700_000_000,
        chat: { id: -1007, type: "supergroup" },
        from: { id: 1, first_name: "Tester", is_bot: false },
        text: "/ping",
        entities: [{ offset: 0, length: 5, type: "bot_command" }],
      },
    }]),
  ]);
  try {
    await Effect.runPromise(Effect.gen(function* () {
      const polling = yield* pollInboxUpdates(bot.handler).pipe(Effect.forkChild);
      yield* Effect.promise(() => fake.whenCalled("getUpdates"));
      yield* TestClock.adjust("30 seconds");
      try {
        const reply = fake.requests.find((request) => request.method === "editMessageText");
        expect(reply?.params).toMatchObject({ chat_id: -1007, text: expect.stringContaining("pong (") });
        const acknowledgment = fake.requests.find((request) =>
          request.method === "getUpdates" &&
          (request.params as { offset?: number } | undefined)?.offset === 9_002
        );
        expect(acknowledgment).toBeDefined();
      } finally {
        yield* Fiber.interrupt(polling);
      }
    }).pipe(
      Effect.provideService(InboxStore, MemoryInbox.make()),
      Effect.provide(Bot.layer({ token: Redacted.make(token), rateLimit: false }).pipe(Layer.provide(fake.layer))),
      Effect.provide(TestClock.layer()),
    ));
  } finally {
    await app.close();
    database.close();
  }
});

test("bot registers every migrated command name", async () => {
  const api = {
    cobaltUrl: "https://cobalt.test",
    goodreadsApiKey: "goodreads-test",
    kieApiKey: "kie-test",
    nanoGptApiKey: "nano-test",
    openrouterApiKey: "openrouter-test",
    waqiApiKey: "waqi-test",
    weatherApiKey: "weather-test",
    wolframAppId: "wolfram-test",
  };
  const { app, bot, database } = await fixture(offline, [], testConfig(api));

  const names = bot.definitions.flatMap((definition) => definition.names).sort();

  await app.close();
  database.close();
  expect(names).toEqual([
    "addquote", "ask", "based", "block", "blocklist", "book", "botstats", "calc", "cat",
    "cron", "d", "define", "dl", "edit", "enable_fts", "football", "fox", "friends",
    "get", "groups", "gstats", "habit", "hb", "help", "highlight", "hl", "hltb",
    "import", "insult", "joke", "meme", "model", "next", "ping", "q", "quote",
    "remind", "search", "seen", "set", "settings", "shiba", "song", "stats", "summon",
    "thinking", "tl", "tldr", "tldw", "tr", "ud", "unblock", "unwhitelist", "users",
    "userstats", "ustat", "ustats", "video", "w", "weather", "whitelist",
  ]);
});

test("help presents enabled commands as a native rich list", async () => {
  const { app, bot, database, fake } = await fixture(offline);

  try {
    await app.run(bot.handler(commandUpdate("/help", 7_001)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("/ping");
  expect(content.text).not.toContain("/based");
  expect(content.text).toContain("Pong.");
  expect(content.types).toContain("list");
});

test("runtime registers every recurring worker", async () => {
  const store = MemoryJobs.make();
  const jobsApp = Application.make({ rateLimit: false, token });
  const { app, bot, database } = await fixture(offline);
  const jobs = runtimeJobs({
    config: testConfig(),
    database,
    http: new Http(offline),
    monotonicMilliseconds: () => 0,
    now: () => new Date("2026-09-01T12:00:00Z"),
    random: () => 0.5,
  }, bot, store);

  await scheduleRuntimeJobs(jobsApp, jobs);
  const cancelled = await Promise.all([
    "cron",
    "footballAlerts",
    "footballSync",
    "habit",
    "quotas",
    "reminders",
    "searchIndex",
    "searchMemory",
  ].map((name) => jobsApp.run(jobs.cancel(name))));
  await jobsApp.close();
  await app.close();
  database.close();

  expect(cancelled).toEqual([true, true, true, true, true, true, true, true]);
});

test("webhook stops cleanly on SIGTERM and removes signal listeners", async () => {
  const signals = new EventEmitter();
  let resolveCompleted: (() => void) | undefined;
  const completed = new Promise<void>((resolve) => {
    resolveCompleted = resolve;
  });
  let stops = 0;
  const waiting = waitForWebhook({
    completed,
    fetch: async () => new Response(),
    stop: async () => {
      stops += 1;
      resolveCompleted?.();
    },
  }, signals);

  signals.emit("SIGTERM");
  await waiting;

  expect(stops).toBe(1);
  expect(signals.listenerCount("SIGINT")).toBe(0);
  expect(signals.listenerCount("SIGTERM")).toBe(0);
});
