import * as Cause from "effect/Cause";
import {
  defineJobs,
  Effect,
  html,
  job,
  Schema,
  sendMessage,
  type Application,
  type JobStoreService,
  type Update,
  type UpdateHandler,
} from "telly";

import { resetCommandLimits } from "./app/command.ts";
import type { AppDependencies } from "./app/dependencies.ts";
import type { createSuperSeriousBot } from "./bot.ts";

type BotRuntime = ReturnType<typeof createSuperSeriousBot>;

export function runtimeJobs(
  dependencies: AppDependencies,
  runtime: BotRuntime,
  store: JobStoreService,
) {
  return defineJobs({
    habit: job({
      payload: Schema.Struct({}),
      run: () => runtime.workers.habit(),
    }),
    quotas: job({
      payload: Schema.Struct({}),
      run: () => resetCommandLimits(dependencies),
    }),
    reminders: job({
      payload: Schema.Struct({}),
      run: () => runtime.workers.reminders(),
    }),
  }, { store });
}

export function scheduleRuntimeJobs(
  app: Application,
  jobs: ReturnType<typeof runtimeJobs>,
) {
  return Effect.all([
    jobs.schedule("reminders", {
      at: new Date("2026-01-01T00:00:00Z"),
      every: "1 minute",
      payload: {},
    }),
    jobs.schedule("habit", {
      at: new Date("2026-01-01T14:30:00Z"),
      every: "1 day",
      payload: {},
    }),
    jobs.schedule("quotas", {
      at: new Date("2026-01-01T18:30:00Z"),
      every: "1 day",
      payload: {},
    }),
  ], { concurrency: "unbounded", discard: true }).pipe((effect) => app.run(effect));
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
