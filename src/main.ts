import { createHash } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import {
  Application,
  Effect,
  getMe,
  setMyCommands,
  setWebhook,
  sendMessage,
  SqliteInbox,
  SqliteJobs,
} from "telly";

import { loadConfig } from "./app/config.ts";
import { Database } from "./app/database.ts";
import type { AppDependencies } from "./app/dependencies.ts";
import { Http } from "./app/http.ts";
import { initializeDatabase } from "./app/schema.ts";
import { createSuperSeriousBot } from "./bot.ts";
import {
  reportUpdateErrors,
  runtimeJobs,
  scheduleRuntimeJobs,
  waitForWebhook,
} from "./runtime.ts";

const allowedUpdates = ["message", "callback_query"] as const;

async function main(): Promise<void> {
  const config = loadConfig();
  await mkdir(config.stateDirectory, { recursive: true });
  const database = Database.open(config);
  await Effect.runPromise(initializeDatabase(database));
  const dependencies: AppDependencies = {
    config,
    database,
    http: new Http(),
    monotonicMilliseconds: performance.now.bind(performance),
    now: () => new Date(),
    random: Math.random,
  };
  const bot = createSuperSeriousBot(dependencies);
  const inbox = await SqliteInbox.open(join(config.stateDirectory, "telly-inbox.db"));
  const jobStore = await SqliteJobs.open(join(config.stateDirectory, "telly-jobs.db"));
  const jobs = runtimeJobs(dependencies, bot, jobStore);
  const app = Application.make({
    ...(config.telegramApiRoot === undefined ? {} : { apiRoot: config.telegramApiRoot }),
    inbox,
    jobs,
    token: config.telegramToken,
  });
  const handler = reportUpdateErrors(bot.handler, config.loggingChannelId);
  try {
    await app.run(setMyCommands({ commands: bot.commands }));
    await scheduleRuntimeJobs(app, jobs);
    const me = await app.run(getMe());
    console.log(`Started @${me.username ?? me.firstName} (${me.id})`);
    if (config.loggingChannelId !== undefined) {
      await app.run(sendMessage({
        chatId: config.loggingChannelId,
        text: `📝 Started @${me.username ?? me.firstName} (${me.id}) at ${new Date().toISOString()}`,
      }));
    }
    if (config.updater === "polling") {
      await app.runPolling(handler, { allowedUpdates });
      return;
    }
    const secretToken = createHash("sha256").update(config.telegramToken).digest("hex");
    const webhook = app.startWebhook(handler, { secretToken });
    const server = Bun.serve({ fetch: webhook.fetch, port: config.port });
    try {
      const baseUrl = config.webhookUrl;
      if (baseUrl === undefined) throw new Error("WEBHOOK_URL must be set for webhook mode");
      await app.run(setWebhook({
        allowedUpdates,
        secretToken,
        url: `${baseUrl.replace(/\/+$/u, "")}/telegram`,
      }));
      console.log(`Webhook listening on port ${config.port}`);
      await waitForWebhook(webhook);
    } finally {
      await server.stop();
    }
  } finally {
    await app.close();
    inbox.close();
    jobStore.close();
    database.close();
  }
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
