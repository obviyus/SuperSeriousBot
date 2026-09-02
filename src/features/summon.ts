import {
  answerCallback,
  callbackData,
  Effect,
  getChatMember,
  html,
  Schema,
  sendMessage,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { callbackRoute } from "../app/callback.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const SummonCallback = callbackData("summon", Schema.Struct({
  action: Schema.Literals(["join", "leave", "resummon"]),
  groupId: Schema.Int,
}));

function summonKeyboard(groupId: number) {
  return {
    inlineKeyboard: [
      [
        { ...SummonCallback.button("✅ Join", { action: "join", groupId }), style: "success" as const },
        { ...SummonCallback.button("❌ Leave", { action: "leave", groupId }), style: "danger" as const },
      ],
      [{ ...SummonCallback.button("🔁 Resummon", { action: "resummon", groupId }), style: "primary" as const }],
    ],
  };
}

function performSummon(
  dependencies: AppDependencies,
  chatId: number,
  groupId: number,
  groupName: string,
) {
  return Effect.gen(function* () {
    const rows = yield* dependencies.database.all(
      `SELECT members.user_id
       FROM summon_group_members members
       JOIN summon_groups groups ON groups.id = members.group_id
       WHERE members.group_id = ? AND groups.chat_id = ?`,
      [groupId, chatId],
    );
    const members = yield* Effect.forEach(rows, (row) =>
      Effect.result(getChatMember({ chatId, userId: rowNumber(row, "user_id") })).pipe(
        Effect.map((result) => result._tag === "Failure" || ["left", "kicked"].includes(
          result.success.status,
        )
          ? undefined
          : `@${result.success.user.username ?? result.success.user.firstName}`),
      ), { concurrency: 8 });
    const active = members.filter((member): member is string => member !== undefined);
    if (active.length === 0) {
      yield* sendMessage({
        chatId,
        parseMode: "HTML",
        replyMarkup: summonKeyboard(groupId),
        text: `No users in group '${html.escape(groupName)}'.`,
      });
      return;
    }
    for (let index = 0; index < active.length; index += 5) {
      const chunk = active.slice(index, index + 5);
      yield* sendMessage({
        chatId,
        parseMode: "HTML",
        ...(index + 5 >= active.length ? { replyMarkup: summonKeyboard(groupId) } : {}),
        text: `[${html.escape(groupName)}] (${active.length} members) ${chunk.map(html.escape).join(" ")}`,
      });
    }
  });
}

export function summonFeature(dependencies: AppDependencies) {
  const lastSummon = new Map<number, number>();
  const definition: CommandDefinition = {
    description: "Tag members of a named group and let people join from buttons.",
    example: "/summon SwitchPlayers",
    names: ["summon"],
    run: Effect.fn("summon")(function* (match) {
      const user = match.message.from;
      if (match.message.chat.type === "private") {
        return yield* answer(match.message, "This command can only be used in group chats.");
      }
      const groupName = match.args[0]?.toLowerCase();
      if (user === undefined || groupName === undefined) {
        return yield* usage(match.message, definition);
      }
      const inserted = yield* dependencies.database.execute(
        `INSERT OR IGNORE INTO summon_groups (group_name, chat_id, creator_id)
         VALUES (?, ?, ?)`,
        [groupName, match.message.chat.id, user.id],
      );
      const row = yield* dependencies.database.one(
        `SELECT id FROM summon_groups
         WHERE group_name = ? COLLATE NOCASE AND chat_id = ?`,
        [groupName, match.message.chat.id],
      );
      if (row === undefined) return yield* Effect.die(new Error("Summon group insert failed"));
      const groupId = rowNumber(row, "id");
      if (inserted.rowsAffected > 0) {
        yield* dependencies.database.execute(
          "INSERT OR IGNORE INTO summon_group_members (group_id, user_id) VALUES (?, ?)",
          [groupId, user.id],
        );
      }
      yield* performSummon(dependencies, match.message.chat.id, groupId, groupName);
      lastSummon.set(groupId, dependencies.monotonicMilliseconds());
    }),
    usage: "/summon [group name]",
  };
  const callback = callbackRoute("summon", SummonCallback, Effect.fn("summonCallback")(function* ({
    callbackQuery,
    data,
  }) {
    if (data.action === "join") {
      yield* dependencies.database.execute(
        "INSERT OR IGNORE INTO summon_group_members (group_id, user_id) VALUES (?, ?)",
        [data.groupId, callbackQuery.from.id],
      );
      yield* answerCallback(callbackQuery, { text: "Joined group." });
      return;
    }
    if (data.action === "leave") {
      yield* dependencies.database.execute(
        "DELETE FROM summon_group_members WHERE group_id = ? AND user_id = ?",
        [data.groupId, callbackQuery.from.id],
      );
      yield* answerCallback(callbackQuery, { text: "Left group." });
      return;
    }
    const last = lastSummon.get(data.groupId);
    const elapsed = last === undefined
      ? Number.POSITIVE_INFINITY
      : dependencies.monotonicMilliseconds() - last;
    if (elapsed < 60_000) {
      yield* answerCallback(callbackQuery, {
        text: `You can only resummon once every 60 seconds. Wait ${Math.ceil((60_000 - elapsed) / 1_000)}s.`,
      });
      return;
    }
    const group = yield* dependencies.database.one(
      "SELECT group_name, chat_id FROM summon_groups WHERE id = ?",
      [data.groupId],
    );
    if (group === undefined) {
      yield* answerCallback(callbackQuery, { text: "Summon group no longer exists." });
      return;
    }
    yield* answerCallback(callbackQuery, { text: "Resummoning..." });
    yield* performSummon(
      dependencies,
      rowNumber(group, "chat_id"),
      data.groupId,
      rowString(group, "group_name"),
    );
    lastSummon.set(data.groupId, dependencies.monotonicMilliseconds());
  }));
  return { callback, commands: [definition] as const };
}
