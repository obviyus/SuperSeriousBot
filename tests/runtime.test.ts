import { EventEmitter } from "node:events";

import { expect, test } from "bun:test";
import { Clock, Fiber, Layer, Redacted, Schema } from "effect";
import { TestClock } from "effect/testing";
import {
  Application,
  Bot,
  defineJobs,
  Effect,
  InboxStore,
  job,
  MemoryInbox,
  MemoryJobs,
  pollInboxUpdates,
} from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { Http } from "../src/app/http.ts";
import {
  recurring,
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
    "addquote", "ask", "based", "block", "blocklist", "book", "calc",
    "dl", "edit", "enable_fts",
    "get", "habit", "hb", "help", "highlight", "hl", "hltb",
    "import", "insult", "joke", "meme", "model", "ping", "q", "quote",
    "remind", "search", "seen", "set", "settings", "song", "stats", "summon",
    "thinking", "tl", "tldr", "tldw", "tr", "ud", "unblock", "unwhitelist",
    "video", "w", "weather", "whitelist",
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
    "habit",
    "quotas",
    "reminders",
    "searchIndex",
    "searchMemory",
  ].map((name) => jobsApp.run(jobs.cancel(name))));
  await jobsApp.close();
  await app.close();
  database.close();

  expect(cancelled).toEqual([true, true, true, true, true]);
});

test("runtime cancels schedules for removed football jobs", async () => {
  const store = MemoryJobs.make();
  const jobsApp = Application.make({ rateLimit: false, token });
  const { app, bot, database } = await fixture(offline);
  const removed = defineJobs({
    footballAlerts: job({ payload: Schema.Struct({}), run: () => Effect.void }),
    footballSync: job({ payload: Schema.Struct({}), run: () => Effect.void }),
  }, { store });
  const jobs = runtimeJobs({
    config: testConfig(),
    database,
    http: new Http(offline),
    monotonicMilliseconds: () => 0,
    now: () => new Date("2026-09-01T12:00:00Z"),
    random: () => 0.5,
  }, bot, store);

  await jobsApp.run(removed.schedule("footballAlerts", { every: "1 minute", payload: {} }));
  await jobsApp.run(removed.schedule("footballSync", { every: "1 day", payload: {} }));
  await scheduleRuntimeJobs(jobsApp, jobs);
  const cancelled = await Promise.all(
    ["footballAlerts", "footballSync"].map((name) => jobsApp.run(jobs.cancel(name))),
  );
  await jobsApp.close();
  await app.close();
  database.close();

  expect(cancelled).toEqual([false, false]);
});

function fixedClock(ms: number): Clock.Clock {
  return {
    currentTimeMillis: Effect.succeed(ms),
    currentTimeMillisUnsafe: () => ms,
    currentTimeNanos: Effect.succeed(BigInt(ms) * 1_000_000n),
    currentTimeNanosUnsafe: () => BigInt(ms) * 1_000_000n,
    monotonicTimeNanos: Effect.succeed(BigInt(ms) * 1_000_000n),
    monotonicTimeNanosUnsafe: () => BigInt(ms) * 1_000_000n,
    sleep: () => Effect.void,
  };
}

test("startup revives a parked recurring job", async () => {
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
  const botId = 123_456;
  const later = <A, E>(effect: Effect.Effect<A, E>) => Effect.runPromise(
    Effect.provideService(effect, Clock.Clock, fixedClock(Date.now() + 2 * 86_400_000)),
  );
  const dueSearchIndex = async () => {
    const lease = await later(store.acquire({ botId, leaseMs: 60_000 }));
    if (lease._tag !== "Acquired") throw new Error("Expected job lease");
    const claimed = await later(store.claim({ botId, fencingToken: lease.fencingToken, limit: 100 }));
    for (const item of claimed) {
      await later(store.settle({
        botId,
        fencingToken: lease.fencingToken,
        id: item.id,
        outcome: item.id === "searchIndex"
          ? { _tag: "Parked", reason: "attempts-exhausted" }
          : { _tag: "Interrupted" },
      }));
    }
    await later(store.release({ botId, fencingToken: lease.fencingToken }));
    return claimed.some((item) => item.id === "searchIndex");
  };

  let claims: Array<boolean> = [];
  try {
    await scheduleRuntimeJobs(jobsApp, jobs);
    claims.push(await dueSearchIndex());
    claims.push(await dueSearchIndex());
    await scheduleRuntimeJobs(jobsApp, jobs);
    claims.push(await dueSearchIndex());
  } finally {
    await jobsApp.close();
    await app.close();
    database.close();
  }

  expect(claims).toEqual([true, false, true]);
});

test("a failing recurring worker finishes so its job is not parked", async () => {
  const definition = recurring("searchIndex", () => Effect.fail(new Error("embedding outage")));
  const symbol = Object.getOwnPropertySymbols(definition)[0];
  if (symbol === undefined) throw new Error("Job definition missing runtime");
  const runtime = Reflect.get(definition, symbol) as {
    execute: (payload: unknown, context: unknown) => Effect.Effect<unknown, unknown>;
  };
  const context = { attempt: 1, id: "searchIndex", scheduledAt: new Date(0) };

  const failed = await Effect.runPromise(Effect.exit(runtime.execute({}, context)));
  const interrupted = await Effect.runPromise(Effect.exit(
    Reflect.get(recurring("searchIndex", () => Effect.interrupt), symbol)
      .execute({}, context) as Effect.Effect<unknown>,
  ));

  expect(failed._tag).toBe("Success");
  expect(interrupted._tag).toBe("Failure");
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
