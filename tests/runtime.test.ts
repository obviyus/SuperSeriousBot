import { EventEmitter } from "node:events";

import { expect, test } from "bun:test";
import { Application, MemoryJobs } from "telly";

import type { Fetch } from "../src/app/http.ts";
import { Http } from "../src/app/http.ts";
import {
  runtimeJobs,
  scheduleRuntimeJobs,
  waitForWebhook,
} from "../src/runtime.ts";
import { fixture, testConfig, token } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

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
    "addquote", "ask", "block", "blocklist", "book", "botstats", "calc", "cat",
    "cron", "d", "define", "dl", "edit", "enable_fts", "football", "fox", "friends",
    "get", "groups", "gstats", "habit", "hb", "help", "highlight", "hl", "hltb",
    "import", "insult", "joke", "meme", "model", "next", "ping", "q", "quote",
    "remind", "search", "seen", "set", "settings", "shiba", "song", "stats", "summon",
    "thinking", "tl", "tldr", "tldw", "tr", "ud", "unblock", "unwhitelist", "users",
    "userstats", "ustat", "ustats", "video", "w", "weather", "whitelist",
  ]);
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
