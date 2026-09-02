import { Effect, html } from "telly";

import { isAdmin } from "../app/admin.ts";
import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { replyBlocks, rich } from "../app/rich.ts";

function adminOnly(dependencies: AppDependencies, userId: number | undefined) {
  return userId !== undefined && isAdmin(dependencies, userId);
}

function blockCommand(dependencies: AppDependencies, remove: boolean): CommandDefinition {
  const definition: CommandDefinition = {
    description: remove
      ? "Unblock a user from a command."
      : "Block a user from a command.",
    example: remove ? "/unblock 123456 weather" : "/block 123456 weather",
    names: [remove ? "unblock" : "block"],
    run: Effect.fn(remove ? "unblockCommand" : "blockCommand")(function* (match) {
      const actor = match.message.from?.id;
      if (!adminOnly(dependencies, actor)) {
        return yield* answer(match.message, "❌ This command is only available to admins");
      }
      if (match.args.length < 2) return yield* usage(match.message, definition);
      const target = Number(match.args[0]);
      if (!Number.isSafeInteger(target)) return yield* answer(match.message, "❌ Invalid user ID");
      const command = match.args[1]?.replace(/^\//u, "").toLowerCase();
      if (command === undefined || command.length === 0) return yield* usage(
        match.message,
        definition,
      );
      if (remove) {
        const result = yield* dependencies.database.execute(
          "DELETE FROM command_blocklist WHERE user_id = ? AND command = ?",
          [target, command],
        );
        return yield* answer(match.message, {
          parseMode: "HTML",
          text: result.rowsAffected > 0
            ? `✅ User <code>${target}</code> unblocked from /${html.escape(command)}`
            : `❓ User <code>${target}</code> was not blocked from /${html.escape(command)}`,
        });
      }
      yield* dependencies.database.execute(
        `INSERT INTO command_blocklist (user_id, command, blocked_by)
         VALUES (?, ?, ?)
         ON CONFLICT(user_id, command) DO NOTHING`,
        [target, command, actor ?? 0],
      );
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `✅ User <code>${target}</code> blocked from using /${html.escape(command)}`,
      });
    }),
    usage: remove
      ? "/unblock <user_id> <command>"
      : "/block <user_id> <command>",
  };
  return definition;
}

function blocklistCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Show all blocked users and commands.",
    example: "/blocklist",
    names: ["blocklist"],
    run: Effect.fn("blocklist")(function* (match) {
      if (!adminOnly(dependencies, match.message.from?.id)) {
        return yield* answer(match.message, "❌ This command is only available to admins");
      }
      const rows = yield* dependencies.database.all(
        `SELECT user_id, command, blocked_by, blocked_at
         FROM command_blocklist ORDER BY blocked_at DESC`,
      );
      if (rows.length === 0) return yield* answer(match.message, "No blocked users found.");
      const table = rich.table([
        ["User", "Command", "Blocked by", "When"],
        ...rows.map((row) => [
          rich.code(String(rowNumber(row, "user_id"))),
          rich.command(`/${rowString(row, "command")}`),
          rich.code(String(rowNumber(row, "blocked_by"))),
          rich.code(rowString(row, "blocked_at")),
        ]),
      ], { header: true });
      return yield* replyBlocks(match.message, [
        rich.heading("🚫 Command blocklist"),
        { ...table, isCompact: true, isStriped: true },
      ]);
    }),
    usage: "/blocklist",
  };
}

function whitelistCommand(dependencies: AppDependencies, remove: boolean): CommandDefinition {
  const definition: CommandDefinition = {
    description: remove
      ? "Remove a chat from a command allow list."
      : "Allow a chat to use a command.",
    example: remove
      ? "/unwhitelist tr -1001234567890"
      : "/whitelist tr -1001234567890",
    names: [remove ? "unwhitelist" : "whitelist"],
    run: Effect.fn(remove ? "unwhitelistCommand" : "whitelistCommand")(function* (match) {
      if (!adminOnly(dependencies, match.message.from?.id)) {
        return yield* answer(match.message, "❌ This command is only available to admins");
      }
      const rawCommand = match.args[0]?.replace(/^\//u, "").toLowerCase();
      if (rawCommand === undefined || rawCommand.length === 0) {
        return yield* usage(match.message, definition);
      }
      const target = match.args[1] === undefined
        ? match.message.chat.id
        : Number(match.args[1]);
      if (!Number.isSafeInteger(target)) {
        return yield* answer(
          match.message,
          "Could not determine target chat. Provide a chat ID explicitly.",
        );
      }
      const result = remove
        ? yield* dependencies.database.execute(
            `DELETE FROM command_whitelist
             WHERE command = ? AND whitelist_type = 'chat' AND whitelist_id = ?`,
            [rawCommand, target],
          )
        : yield* dependencies.database.execute(
            `INSERT OR IGNORE INTO command_whitelist (command, whitelist_type, whitelist_id)
             VALUES (?, 'chat', ?)`,
            [rawCommand, target],
          );
      const action = remove
        ? result.rowsAffected > 0
          ? "Removed chat"
          : "Chat was not whitelisted"
        : result.rowsAffected > 0
        ? "Added chat"
        : "Chat is already whitelisted";
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `${remove && result.rowsAffected === 0 ? "❓" : "✅"} ${action} <code>${target}</code> ${remove ? "from" : "for"} /${html.escape(rawCommand)}`,
      });
    }),
    usage: remove
      ? "/unwhitelist <command> [chat_id]"
      : "/whitelist <command> [chat_id]",
  };
  return definition;
}

export function moderationCommands(
  dependencies: AppDependencies,
): ReadonlyArray<CommandDefinition> {
  return [
    blockCommand(dependencies, false),
    blockCommand(dependencies, true),
    blocklistCommand(dependencies),
    whitelistCommand(dependencies, false),
    whitelistCommand(dependencies, true),
  ];
}
