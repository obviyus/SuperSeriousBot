import { CronExpressionParser } from "cron-parser";
import {
  answerCallback,
  callbackData,
  callbackTarget,
  editMessageReplyMarkup,
  editMessageText,
  Effect,
  html,
  Schema,
} from "telly";

import { Ai } from "../app/ai.ts";
import { callbackRoute, ignoreUnchangedMessage } from "../app/callback.ts";
import {
  answer,
  type CommandDefinition,
  useCommandQuota,
  usage,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { richMarkdownPrompt, sendRich } from "../app/rich.ts";

const defaultTimezone = "Asia/Kolkata";
const CronDraft = Schema.Struct({
  cronExpr: Schema.String,
  task: Schema.String,
  timezone: Schema.String,
  title: Schema.String,
});
const CronCallback = callbackData("cron", Schema.Struct({ taskId: Schema.Int }));

interface CronTask {
  readonly chatId: number;
  readonly cronExpr: string;
  readonly id: number;
  readonly task: string;
  readonly timezone: string;
  readonly title: string;
  readonly userId: number;
}

function nextRun(expression: string, timezone: string, now: Date): number {
  return Math.floor(CronExpressionParser.parse(expression, {
    currentDate: now,
    tz: timezone,
  }).next().toDate().getTime() / 1_000);
}

function taskFromRow(row: import("@libsql/client").Row): CronTask {
  return {
    chatId: rowNumber(row, "chat_id"),
    cronExpr: rowString(row, "cron_expr"),
    id: rowNumber(row, "id"),
    task: rowString(row, "task"),
    timezone: rowString(row, "timezone"),
    title: rowString(row, "title"),
    userId: rowNumber(row, "user_id"),
  };
}

function loadTask(dependencies: AppDependencies, id: number) {
  return dependencies.database.one(
    `SELECT id, chat_id, user_id, title, task, cron_expr, timezone
     FROM cron_tasks WHERE id = ? AND enabled = 1`,
    [id],
  ).pipe(Effect.map((row) => row === undefined ? undefined : taskFromRow(row)));
}

function deleteKeyboard(taskId: number) {
  return {
    inlineKeyboard: [[{
      ...CronCallback.button("🗑️ Delete", { taskId }),
      style: "danger" as const,
    }]],
  };
}

function runTask(dependencies: AppDependencies, ai: Ai, task: CronTask) {
  return Effect.gen(function* () {
    const historyRows = yield* dependencies.database.all(
      `SELECT status, result_text, error_text, finish_time FROM cron_runs
       WHERE cron_task_id = ? ORDER BY id DESC LIMIT 5`,
      [task.id],
    );
    const history = [...historyRows].reverse().map((row, index) =>
      `${index + 1}. ${rowString(row, "finish_time")} [${rowString(row, "status")}]\n${String(row["result_text"] ?? row["error_text"] ?? "No output recorded.")}`
    ).join("\n\n") || "No previous runs.";
    const start = dependencies.now().toISOString();
    const result = yield* ai.complete("cron", [
      { content: richMarkdownPrompt, role: "system" },
      {
        content: "Run the saved task now. Be concise but complete. Return only the Telegram message to send.",
        role: "system",
      },
      {
        content: `Title: ${task.title}\n\nTask:\n${task.task}\n\nPrevious runs:\n${history}`,
        role: "user",
      },
    ], { maxTokens: 1_000 });
    if (result.trim().length === 0) return yield* Effect.die(new Error("AI returned no cron result"));
    const usernameRow = yield* dependencies.database.one(
      "SELECT username FROM user_stats WHERE user_id = ?",
      [task.userId],
    );
    const username = usernameRow === undefined ? String(task.userId) : rowString(usernameRow, "username");
    yield* sendRich(
      task.chatId,
      `⏰ **${task.title}**\n\n${result.trim()}\n\n@${username}`,
      {
        documentName: "cron-result.txt",
        replyMarkup: deleteKeyboard(task.id),
      },
    );
    yield* dependencies.database.execute(
      `INSERT INTO cron_runs (
        cron_task_id, status, result_text, start_time, finish_time
      ) VALUES (?, 'success', ?, ?, ?)`,
      [task.id, result.trim(), start, dependencies.now().toISOString()],
    );
  });
}

export function cronFeature(dependencies: AppDependencies) {
  const ai = new Ai(dependencies);
  const definition: CommandDefinition = {
    apiKey: "openrouterApiKey",
    availability: "whitelist-private",
    description: "Create and manage scheduled AI tasks.",
    example: "/cron daily 9am check the DJI Osmo Pocket 4 price",
    names: ["cron"],
    run: Effect.fn("cron")(function* (match) {
      const user = match.message.from;
      if (user === undefined) return;
      if (match.args.length === 0) {
        const rows = yield* dependencies.database.all(
          `SELECT id, title, cron_expr, timezone, next_run_time FROM cron_tasks
           WHERE chat_id = ? AND user_id = ? AND enabled = 1 ORDER BY id`,
          [match.message.chat.id, user.id],
        );
        if (rows.length === 0) return yield* usage(match.message, definition);
        const entries = rows.map((row) =>
          `<code>${rowNumber(row, "id")}</code>. <b>${html.escape(rowString(row, "title"))}</b>\n<code>${html.escape(rowString(row, "cron_expr"))}</code> <code>${html.escape(rowString(row, "timezone"))}</code>\nNext: <tg-time unix="${rowNumber(row, "next_run_time")}" format="wDT">scheduled</tg-time>`
        );
        return yield* answer(match.message, {
          parseMode: "HTML",
          text: `<b>Your cron tasks in this chat:</b>\n\n${entries.join("\n\n")}`,
        });
      }
      const action = match.args[0]?.toLowerCase();
      if (action === "del" || action === "run") {
        const id = Number(match.args[1]);
        if (!Number.isSafeInteger(id) || id < 1) {
          return yield* answer(match.message, "Cron task id must be a positive number.");
        }
        const task = yield* loadTask(dependencies, id);
        if (task === undefined || task.chatId !== match.message.chat.id || task.userId !== user.id) {
          return yield* answer(match.message, "Cron task not found.");
        }
        if (action === "del") {
          yield* dependencies.database.execute(
            "UPDATE cron_tasks SET enabled = 0, update_time = CURRENT_TIMESTAMP WHERE id = ?",
            [id],
          );
          return yield* answer(match.message, {
            parseMode: "HTML",
            text: `Deleted cron task <code>${id}</code>.`,
          });
        }
        if (!(yield* useCommandQuota(dependencies, match.message, "cron", 20))) return;
        yield* answer(match.message, { parseMode: "HTML", text: `Running cron task <code>${id}</code>...` });
        yield* runTask(dependencies, ai, task);
        return;
      }
      if (!(yield* useCommandQuota(dependencies, match.message, "cron", 20))) return;
      const status = yield* answer(match.message, "Creating cron task...");
      const draft = yield* ai.object("cron", [
        {
          content: `Convert the request into one durable cron task. Use standard five-field cron syntax and an IANA timezone. Use ${defaultTimezone} when no timezone is explicit. Return a short title, complete task, cronExpr, and timezone.`,
          role: "system",
        },
        { content: `Current time: ${dependencies.now().toISOString()}\n\nRequest:\n${match.argText}`, role: "user" },
      ], CronDraft, { maxTokens: 500 }).pipe(
        Effect.flatMap((value) => Effect.try({
          try: () => ({
            ...value,
            next: nextRun(value.cronExpr, value.timezone, dependencies.now()),
          }),
          catch: (error) => new Error(error instanceof Error ? error.message : String(error)),
        })),
      );
      const inserted = yield* dependencies.database.execute(
        `INSERT INTO cron_tasks (
          chat_id, user_id, title, task, cron_expr, timezone, next_run_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          match.message.chat.id,
          user.id,
          draft.title.trim(),
          draft.task.trim(),
          draft.cronExpr.trim(),
          draft.timezone.trim(),
          draft.next,
        ],
      );
      if (inserted.lastInsertRowid === undefined) return yield* Effect.die(
        new Error("Cron insert returned no id"),
      );
      const id = Number(inserted.lastInsertRowid);
      yield* editMessageText({
        chatId: status.chat.id,
        messageId: status.messageId,
        parseMode: "HTML",
        text: `Created cron task <code>${id}</code>.\n\n<b>${html.escape(draft.title)}</b>\n<code>${html.escape(draft.cronExpr)}</code> <code>${html.escape(draft.timezone)}</code>\nNext: <tg-time unix="${draft.next}" format="wDT">scheduled</tg-time>`,
      });
    }),
    usage: "/cron [schedule + task]\n/cron del [id]\n/cron run [id]",
  };
  const callback = callbackRoute("cron", CronCallback, Effect.fn("cronCallback")(function* ({
    callbackQuery,
    data,
  }) {
    const task = yield* loadTask(dependencies, data.taskId);
    if (task === undefined) {
      yield* answerCallback(callbackQuery, { text: "Cron task already deleted." });
    } else if (task.userId !== callbackQuery.from.id) {
      yield* answerCallback(callbackQuery, { text: "You can only delete your own cron tasks." });
      return;
    } else {
      yield* dependencies.database.execute(
        "UPDATE cron_tasks SET enabled = 0, update_time = CURRENT_TIMESTAMP WHERE id = ?",
        [task.id],
      );
      yield* answerCallback(callbackQuery, { text: "Deleted cron task." });
    }
    const target = callbackTarget(callbackQuery);
    if ("ephemeralMessageId" in target) return;
    yield* ignoreUnchangedMessage(editMessageReplyMarkup({ ...target }));
  }));
  const worker = Effect.fn("cronWorker")(function* () {
    const now = Math.floor(dependencies.now().getTime() / 1_000);
    const rows = yield* dependencies.database.all(
      `SELECT id, chat_id, user_id, title, task, cron_expr, timezone
       FROM cron_tasks
       WHERE enabled = 1 AND next_run_time <= ?
         AND (claim_time IS NULL OR claim_time <= ?)
       ORDER BY next_run_time LIMIT 20`,
      [now, now - 300],
    );
    for (const row of rows) {
      const task = taskFromRow(row);
      const claimed = yield* dependencies.database.execute(
        `UPDATE cron_tasks SET claim_time = ?, attempt_count = attempt_count + 1
         WHERE id = ? AND enabled = 1 AND (claim_time IS NULL OR claim_time <= ?)`,
        [now, task.id, now - 300],
      );
      if (claimed.rowsAffected === 0) continue;
      const result = yield* Effect.result(runTask(dependencies, ai, task));
      if (result._tag === "Failure") {
        yield* dependencies.database.execute(
          `INSERT INTO cron_runs (
            cron_task_id, status, error_text, start_time, finish_time
          ) VALUES (?, 'error', ?, ?, ?)`,
          [task.id, String(result.failure), dependencies.now().toISOString(), dependencies.now().toISOString()],
        );
      }
      yield* dependencies.database.execute(
        `UPDATE cron_tasks SET next_run_time = ?, claim_time = NULL,
          update_time = CURRENT_TIMESTAMP WHERE id = ?`,
        [nextRun(task.cronExpr, task.timezone, dependencies.now()), task.id],
      );
    }
  });
  return { callback, commands: [definition] as const, worker };
}
