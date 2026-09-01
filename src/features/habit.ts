import {
  answerCallback,
  callbackData,
  callbackTarget,
  editMessageText,
  Effect,
  Schema,
  sendMessage,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { callbackRoute, ignoreUnchangedMessage } from "../app/callback.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const HabitCallback = callbackData("habit", Schema.Struct({
  action: Schema.Literals(["checkin", "leave"]),
  habitId: Schema.Int,
}));

function habitKeyboard(habitId: number) {
  return {
    inlineKeyboard: [
      [{ ...HabitCallback.button("📅 Check-in", { action: "checkin", habitId }), style: "success" as const }],
      [{ ...HabitCallback.button("❌ Leave", { action: "leave", habitId }), style: "danger" as const }],
    ],
  };
}

function habitMessage(dependencies: AppDependencies, habitId: number) {
  return dependencies.database.all(
    `SELECT h.habit_name, h.weekly_goal, members.user_id,
            COALESCE(users.username, CAST(members.user_id AS TEXT)) AS username,
            (SELECT COUNT(*) FROM habit_log logs
             WHERE logs.habit_id = h.id AND logs.user_id = members.user_id
             AND logs.create_time >= DATETIME('now', 'weekday 0', 'start of day', '-6 days')) AS week_count
     FROM habit h
     JOIN habit_members members ON h.id = members.habit_id
     LEFT JOIN user_stats users ON users.user_id = members.user_id
     WHERE h.id = ?`,
    [habitId],
  ).pipe(Effect.map((rows) => {
    const first = rows[0];
    if (first === undefined) return "Habit not found.";
    const goal = rowNumber(first, "weekly_goal");
    const members = rows.map((row) => {
      const count = rowNumber(row, "week_count");
      const status = count > goal ? "🚀" : count < goal ? "⌛" : "✅";
      return `- ${status} ${count}/${goal} @${rowString(row, "username")}`;
    });
    return `📅 #${rowString(first, "habit_name")} 📅\n\n${members.join("\n")}`;
  }));
}

export function habitFeature(dependencies: AppDependencies) {
  const definition: CommandDefinition = {
    description: "Create or join a weekly habit in this group.",
    example: "/habit workout 5",
    names: ["habit", "hb"],
    run: Effect.fn("habit")(function* (match) {
      const user = match.message.from;
      const habitName = match.args[0];
      const goal = Number(match.args[1]);
      if (user === undefined || habitName === undefined || match.args[1] === undefined) {
        return yield* usage(match.message, definition);
      }
      if (!Number.isInteger(goal) || goal < 1 || goal > 7) {
        return yield* answer(match.message, "Please enter a number between 1 and 7.");
      }
      const existing = yield* dependencies.database.one(
        "SELECT id FROM habit WHERE chat_id = ? AND habit_name = ?",
        [match.message.chat.id, habitName],
      );
      let habitId: number;
      let created = false;
      if (existing === undefined) {
        const inserted = yield* dependencies.database.execute(
          "INSERT INTO habit (chat_id, habit_name, weekly_goal, creator_id) VALUES (?, ?, ?, ?)",
          [match.message.chat.id, habitName, goal, user.id],
        );
        if (inserted.lastInsertRowid === undefined) {
          return yield* Effect.die(new Error("Habit insert returned no id"));
        }
        habitId = Number(inserted.lastInsertRowid);
        created = true;
      } else {
        habitId = rowNumber(existing, "id");
      }
      yield* dependencies.database.execute(
        "INSERT OR IGNORE INTO habit_members (habit_id, user_id) VALUES (?, ?)",
        [habitId, user.id],
      );
      yield* answer(
        match.message,
        created
          ? `Created a new habit #${habitName} with a goal of ${goal} days per week.`
          : "A habit with this name already exists in this group. Adding you to it...",
      );
      yield* answer(match.message, {
        replyMarkup: habitKeyboard(habitId),
        text: yield* habitMessage(dependencies, habitId),
      });
    }),
    usage: "/habit [habit name] [days per week]",
  };
  const callback = callbackRoute("habit", HabitCallback, Effect.fn("habitCallback")(function* ({
    callbackQuery,
    data,
  }) {
    if (data.action === "checkin") {
      yield* dependencies.database.execute(
        "INSERT OR IGNORE INTO habit_members (habit_id, user_id) VALUES (?, ?)",
        [data.habitId, callbackQuery.from.id],
      );
      const existing = yield* dependencies.database.one(
        `SELECT 1 FROM habit_log
         WHERE habit_id = ? AND user_id = ?
         AND create_time > DATETIME('now', 'start of day')`,
        [data.habitId, callbackQuery.from.id],
      );
      if (existing === undefined) {
        yield* dependencies.database.execute(
          "INSERT INTO habit_log (habit_id, user_id) VALUES (?, ?)",
          [data.habitId, callbackQuery.from.id],
        );
        yield* answerCallback(callbackQuery, { text: "Checked in successfully!" });
      } else {
        yield* answerCallback(callbackQuery, { text: "You have already checked in today." });
      }
    } else {
      yield* dependencies.database.execute(
        "DELETE FROM habit_members WHERE habit_id = ? AND user_id = ?",
        [data.habitId, callbackQuery.from.id],
      );
      yield* answerCallback(callbackQuery, { text: "You've left the habit." });
    }
    const target = callbackTarget(callbackQuery);
    if ("ephemeralMessageId" in target) return;
    yield* ignoreUnchangedMessage(editMessageText({
      ...target,
      replyMarkup: habitKeyboard(data.habitId),
      text: yield* habitMessage(dependencies, data.habitId),
    }));
  }));
  const worker = Effect.fn("habitWorker")(function* () {
    const rows = yield* dependencies.database.all(
      "SELECT * FROM habit WHERE id IN (SELECT DISTINCT habit_id FROM habit_members)",
    );
    for (const row of rows) {
      const habitId = rowNumber(row, "id");
      const delivered = yield* Effect.result(sendMessage({
        chatId: rowNumber(row, "chat_id"),
        replyMarkup: habitKeyboard(habitId),
        text: yield* habitMessage(dependencies, habitId),
      }));
      if (
        delivered._tag === "Failure" &&
        delivered.failure.reason._tag === "TelegramRejected" &&
        delivered.failure.reason.description.toLowerCase().includes("chat not found")
      ) {
        yield* dependencies.database.batch([
          { sql: "DELETE FROM habit_log WHERE habit_id = ?", args: [habitId] },
          { sql: "DELETE FROM habit_members WHERE habit_id = ?", args: [habitId] },
          { sql: "DELETE FROM habit WHERE id = ?", args: [habitId] },
        ]);
      }
    }
  });
  return { callback, commands: [definition] as const, worker };
}
