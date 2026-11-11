import * as Cause from "effect/Cause";
import {
  defineJobs,
  Effect,
  html,
  job,
  Schema,
  sendMessage,
  type Application,
  type Bot,
  type JobStoreService,
  type Update,
  type UpdateHandler,
  type Webhook,
} from "telly";

import { resetCommandLimits } from "./app/command.ts";
import type { AppDependencies } from "./app/dependencies.ts";
import type { createSuperSeriousBot } from "./bot.ts";

type BotRuntime = ReturnType<typeof createSuperSeriousBot>;

export interface ShutdownSignals {
  readonly off: (event: "SIGINT" | "SIGTERM", listener: () => void) => unknown;
  readonly once: (event: "SIGINT" | "SIGTERM", listener: () => void) => unknown;
}

export async function waitForWebhook(
  webhook: Webhook,
  signals?: ShutdownSignals,
): Promise<void> {
  const source = signals ?? {
    off: (event: "SIGINT" | "SIGTERM", listener: () => void) =>
      Reflect.apply(process.removeListener, process, [event, listener]),
    once: (event: "SIGINT" | "SIGTERM", listener: () => void) => event === "SIGINT"
      ? process.once("SIGINT", listener)
      : process.once("SIGTERM", listener),
  };
  const stop = () => {
    webhook.stop().catch(() => undefined);
  };
  source.once("SIGINT", stop);
  source.once("SIGTERM", stop);
  try {
    await webhook.completed;
  } finally {
    source.off("SIGINT", stop);
    source.off("SIGTERM", stop);
  }
}

// Recurring workers are idempotent sweeps. A failed run is logged and the next
// interval retries it; letting it fail would park the job permanently once
// Telly's attempts are exhausted.
export function recurring<E>(name: string, run: () => Effect.Effect<unknown, E, Bot>) {
  return job({
    payload: Schema.Struct({}),
    run: () => Effect.suspend(run).pipe(
      Effect.catchCause((cause) => Cause.hasInterruptsOnly(cause)
        ? Effect.failCause(cause)
        : Effect.logError("Recurring job failed").pipe(
            Effect.annotateLogs({ cause: Cause.pretty(cause), job: name }),
          )),
    ),
  });
}

export function runtimeJobs(
  dependencies: AppDependencies,
  runtime: BotRuntime,
  store: JobStoreService,
) {
  return defineJobs({
    habit: recurring("habit", () => runtime.workers.habit()),
    cron: recurring("cron", () => runtime.workers.cron()),
    quotas: recurring("quotas", () => resetCommandLimits(dependencies)),
    reminders: recurring("reminders", () => runtime.workers.reminders()),
    searchIndex: recurring("searchIndex", () => runtime.workers.search.index()),
    searchMemory: recurring("searchMemory", () => runtime.workers.search.memory()),
  }, { store });
}

// Repeating jobs persist by name. Cancel removed ones so the worker does not
// retry a job it can no longer run.
const retiredJobs = ["footballAlerts", "footballSync"] as const;

const schedules = [
  ["reminders", "00:00:00", "1 minute"],
  ["cron", "00:00:00", "1 minute"],
  ["habit", "14:30:00", "1 day"],
  ["quotas", "18:30:00", "1 day"],
  ["searchIndex", "00:00:30", "15 minutes"],
  ["searchMemory", "03:00:00", "1 day"],
] as const;

// Scheduling an existing job ID is a no-op, even when that job is parked.
// Re-create every recurring job on startup so a parked one resumes; the
// anchored schedule picks the next future slot, so nothing runs early.
export function scheduleRuntimeJobs(
  app: Application,
  jobs: ReturnType<typeof runtimeJobs>,
) {
  const stale = [...retiredJobs, ...schedules.map(([name]) => name)];
  return app.run(Effect.forEach(stale, (id) => jobs.cancel(id), { discard: true }).pipe(
    Effect.andThen(Effect.forEach(schedules, ([name, time, every]) => jobs.schedule(name, {
      at: new Date(`2026-01-01T${time}Z`),
      every,
      payload: {},
    }), { concurrency: "unbounded", discard: true })),
  ));
}

export function reportUpdateErrors(
  handler: UpdateHandler<unknown>,
  loggingChannelId: number | undefined,
): UpdateHandler<unknown, void> {
  return (update: Update) => handler(update).pipe(
    Effect.asVoid,
    Effect.catchCause((cause) => {
      if (Cause.hasInterruptsOnly(cause)) return Effect.failCause(cause);
      const report = loggingChannelId === undefined
        ? Effect.void
        : sendMessage({
            chatId: loggingChannelId,
            parseMode: "HTML",
            text: `<b>Update failed</b>\n\n<pre>${html.escape(JSON.stringify(update).slice(0, 1_500))}</pre>\n\n<pre>${html.escape(Cause.pretty(cause).slice(0, 1_500))}</pre>`,
          }).pipe(
            Effect.catch(() => Effect.logError("Failed to send update error report")),
            Effect.asVoid,
          );
      return Effect.logError("Update handler failed").pipe(
        Effect.andThen(report),
      );
    }),
  );
}
