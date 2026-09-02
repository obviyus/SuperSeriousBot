import { parseDate } from "chrono-node";
import {
  Effect,
  html,
  sendMessage,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const claimLeaseSeconds = 5 * 60;
const maximumAttempts = 5;

function telegramTime(unix: number, fallback: string, format?: string): string {
  const formatAttribute = format === undefined ? "" : ` format="${format}"`;
  return `<tg-time unix="${unix}"${formatAttribute}>${html.escape(fallback)}</tg-time>`;
}

export function parseReminderTime(text: string, now: Date): Date | undefined {
  const hasIst = /\bIST\b/iu.test(text);
  const normalized = text.replace(/\bIST\b/giu, "").trim();
  return parseDate(
    normalized,
    { instant: now, timezone: hasIst ? 330 : 0 },
    { forwardDate: true },
  ) ?? undefined;
}

export function reminderFeature(dependencies: AppDependencies) {
  const definition: CommandDefinition = {
    description: "Create a reminder with a trigger time for this group.",
    example: "/remind Japan Trip - 5 months later",
    names: ["remind"],
    run: Effect.fn("remind")(function* (match) {
      const user = match.message.from;
      if (user === undefined) return;
      if (match.argText.length === 0) {
        const rows = yield* dependencies.database.all(
          `SELECT title, target_time FROM reminders
           WHERE user_id = ? AND chat_id = ? ORDER BY target_time`,
          [user.id, match.message.chat.id],
        );
        if (rows.length === 0) return yield* usage(match.message, definition);
        const items = rows.map((row, index) => {
          const target = rowNumber(row, "target_time");
          const fallback = new Date(target * 1_000).toISOString().replace("T", " ").slice(0, 16);
          return `${index + 1}. <code>${html.escape(rowString(row, "title"))}</code> ${telegramTime(target, `${fallback} UTC`, "r")}`;
        });
        return yield* answer(match.message, {
          parseMode: "HTML",
          text: `⏰ Your reminders in this chat:\n\n${items.join("\n")}`,
        });
      }
      const separator = match.argText.indexOf(" - ");
      if (separator === -1) return yield* usage(match.message, definition);
      const title = match.argText.slice(0, separator).trim();
      const timeText = match.argText.slice(separator + 3).trim();
      const now = dependencies.now();
      const target = parseReminderTime(timeText, now);
      if (target === undefined) {
        return yield* answer(
          match.message,
          "Invalid date/time format. Please provide a valid date and time.",
        );
      }
      if (target.getTime() < now.getTime()) {
        return yield* answer(
          match.message,
          "The specified time is in the past. Please provide a future date and time.",
        );
      }
      const unix = Math.floor(target.getTime() / 1_000);
      yield* dependencies.database.execute(
        "INSERT INTO reminders (chat_id, user_id, title, target_time) VALUES (?, ?, ?, ?)",
        [match.message.chat.id, user.id, title, unix],
      );
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `I will remind you about <code>${html.escape(title)}</code> on ${telegramTime(unix, target.toISOString(), "wDT")}`,
      });
    }),
    usage: "/remind [reminder name] - [target time]",
  };
  const worker = Effect.fn("reminderWorker")(function* () {
    const now = Math.floor(dependencies.now().getTime() / 1_000);
    const rows = yield* dependencies.database.all(
      `SELECT id, title, target_time, user_id, chat_id FROM reminders
       WHERE target_time <= ? AND attempt_count < ?
         AND (claim_time IS NULL OR claim_time <= ?)
       ORDER BY target_time LIMIT 50`,
      [now, maximumAttempts, now - claimLeaseSeconds],
    );
    for (const row of rows) {
      const id = rowNumber(row, "id");
      const claimed = yield* dependencies.database.execute(
        `UPDATE reminders SET claim_time = ?, attempt_count = attempt_count + 1, last_error = NULL
         WHERE id = ? AND (claim_time IS NULL OR claim_time <= ?)`,
        [now, id, now - claimLeaseSeconds],
      );
      if (claimed.rowsAffected === 0) continue;
      const userId = rowNumber(row, "user_id");
      const chatId = rowNumber(row, "chat_id");
      const text = `⏰ <a href="tg://user?id=${userId}">Reminder for you</a>\n\n<code>${html.escape(rowString(row, "title"))}</code>`;
      const delivered = yield* Effect.result(sendMessage({ chatId, parseMode: "HTML", text }));
      if (delivered._tag === "Success") {
        yield* dependencies.database.execute("DELETE FROM reminders WHERE id = ?", [id]);
        continue;
      }
      const migration = delivered.failure.reason._tag === "TelegramRejected"
        ? delivered.failure.reason.migrateToChatId
        : undefined;
      if (migration !== undefined) {
        yield* dependencies.database.execute(
          "UPDATE reminders SET chat_id = ? WHERE chat_id = ?",
          [migration, chatId],
        );
        const retried = yield* Effect.result(sendMessage({
          chatId: migration,
          parseMode: "HTML",
          text,
        }));
        if (retried._tag === "Success") {
          yield* dependencies.database.execute("DELETE FROM reminders WHERE id = ?", [id]);
          continue;
        }
      }
      yield* dependencies.database.execute(
        "UPDATE reminders SET last_error = ? WHERE id = ?",
        [delivered.failure.message, id],
      );
    }
  });
  return { commands: [definition] as const, worker };
}
