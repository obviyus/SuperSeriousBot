import { Effect, getMe, html } from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

function readableTime(now: Date, input: string): string {
  const seconds = Math.abs(now.getTime() - new Date(input).getTime()) / 1_000;
  for (const [limit, unit, divisor] of [
    [60, "second", 1],
    [3_600, "minute", 60],
    [86_400, "hour", 3_600],
    [604_800, "day", 86_400],
    [31_536_000, "week", 604_800],
    [Number.POSITIVE_INFINITY, "year", 31_536_000],
  ] as const) {
    if (seconds >= limit) continue;
    const value = Number((seconds / divisor).toFixed(1));
    return `${value} ${unit}${value > 1 ? "s" : ""}`;
  }
  return "0 seconds";
}

function statsCommand(dependencies: AppDependencies, todayOnly: boolean): CommandDefinition {
  return {
    description: todayOnly
      ? "Get message count by user for the last day."
      : "Get total message count by user in this group.",
    example: todayOnly ? "/stats" : "/gstats",
    names: [todayOnly ? "stats" : "gstats"],
    run: Effect.fn(todayOnly ? "dailyStats" : "groupStats")(function* (match) {
      const time = todayOnly
        ? "AND create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime')"
        : "";
      const rows = yield* dependencies.database.all(
        `SELECT cs.user_id, COUNT(*) AS user_count,
                COALESCE(us.first_name, us.username, CAST(cs.user_id AS TEXT)) AS name
         FROM chat_stats cs
         LEFT JOIN user_stats us ON us.user_id = cs.user_id
         WHERE cs.chat_id = ? ${time}
         GROUP BY cs.user_id
         ORDER BY COUNT(*) DESC
         LIMIT 10`,
        [match.message.chat.id],
      );
      const total = rows.reduce((sum, row) => sum + rowNumber(row, "user_count"), 0);
      if (total === 0) return yield* answer(match.message, "No messages recorded.");
      const title = match.message.chat.title ?? String(match.message.chat.id);
      const lines = rows.map((row) => {
        const count = rowNumber(row, "user_count");
        return `<code>${(count / total * 100).toFixed(1).padStart(4)}% - ${html.escape(rowString(row, "name"))}</code>`;
      });
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `Stats for <b>${html.escape(title)}:</b>\n\n${lines.join("\n")}\n\nTotal messages: <b>${total}</b>`,
      });
    }),
    usage: todayOnly ? "/stats" : "/gstats",
  };
}

function seenCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Get the time since a user's last message in this chat.",
    example: "/seen @obviyus",
    names: ["seen"],
    run: Effect.fn("seen")(function* (match) {
      const username = match.args[0]?.replace(/^@/u, "").toLowerCase();
      if (username === undefined || username.length === 0) {
        return yield* usage(match.message, definition);
      }
      const row = yield* dependencies.database.one(
        `SELECT us.user_id, us.username, cs.message_id, cs.create_time
         FROM user_stats us
         JOIN chat_stats cs ON cs.user_id = us.user_id AND cs.chat_id = ?
         WHERE LOWER(us.username) = ?
         ORDER BY cs.id DESC LIMIT 1`,
        [match.message.chat.id, username],
      );
      if (row === undefined) {
        return yield* answer(match.message, `@${username} has never been seen in this chat.`);
      }
      const messageId = rowNumber(row, "message_id");
      const chatId = String(match.message.chat.id);
      const messageLink = match.message.chat.username === undefined && chatId.startsWith("-100")
        ? `https://t.me/c/${chatId.slice(4)}/${messageId}`
        : match.message.chat.username === undefined
        ? undefined
        : `https://t.me/${match.message.chat.username}/${messageId}`;
      const link = messageLink === undefined ? "" : `\n\n🔗 <a href="${messageLink}">Link</a>`;
      return yield* answer(match.message, {
        linkPreviewOptions: { isDisabled: true },
        parseMode: "HTML",
        text: `Last message from <a href="tg://user?id=${rowNumber(row, "user_id")}">${html.escape(rowString(row, "username"))}</a> was ${readableTime(dependencies.now(), rowString(row, "create_time"))} ago.${link}`,
      });
    }),
    usage: "/seen [username]",
  };
  return definition;
}

function totalCommand(dependencies: AppDependencies, users: boolean): CommandDefinition {
  return {
    description: users
      ? "Get the number of users that use this bot."
      : "Get the number of groups that use this bot.",
    example: users ? "/users" : "/groups",
    names: [users ? "users" : "groups"],
    run: Effect.fn(users ? "totalUsers" : "totalGroups")(function* (match) {
      const bot = yield* getMe();
      const row = yield* dependencies.database.one(
        `SELECT COUNT(DISTINCT ${users ? "user_id" : "chat_id"}) AS total FROM chat_stats`,
      );
      const total = row === undefined ? 0 : rowNumber(row, "total");
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: users
          ? `@${bot.username ?? bot.firstName} is used by <b>${total}</b> users.`
          : `@${bot.username ?? bot.firstName} is used in <b>${total}</b> groups.`,
      });
    }),
    usage: users ? "/users" : "/groups",
  };
}

function botStatsCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Get usage counts for bot commands.",
    example: "/botstats",
    names: ["botstats"],
    run: Effect.fn("botStats")(function* (match) {
      const bot = yield* getMe();
      const rows = yield* dependencies.database.all(
        `SELECT command, COUNT(*) AS command_count
         FROM command_stats GROUP BY command ORDER BY command_count DESC LIMIT 10`,
      );
      const totalRow = yield* dependencies.database.one("SELECT COUNT(*) AS total FROM command_stats");
      const lines = rows.map((row) =>
        `<code>${String(rowNumber(row, "command_count")).padStart(4)} - /${html.escape(rowString(row, "command"))}</code>`
      );
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `Stats for <b>@${html.escape(bot.username ?? bot.firstName)}:</b>\n\n${lines.join("\n")}\n\nTotal: <b>${totalRow === undefined ? 0 : rowNumber(totalRow, "total")}</b>`,
      });
    }),
    usage: "/botstats",
  };
}

function friendsCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Show your strongest connections in this group's social graph.",
    example: "/friends",
    names: ["friends"],
    run: Effect.fn("friends")(function* (match) {
      const user = match.message.from;
      if (user === undefined) return;
      const rows = yield* dependencies.database.all(
        `SELECT other_id, direction, SUM(weight) AS weight,
                COALESCE(us.first_name, us.username, CAST(other_id AS TEXT)) AS name
         FROM (
           SELECT mentioned_user_id AS other_id, 'out' AS direction, COUNT(*) AS weight
           FROM chat_mentions
           WHERE chat_id = ? AND mentioning_user_id = ? AND mentioned_user_id != ?
           GROUP BY mentioned_user_id
           UNION ALL
           SELECT mentioning_user_id AS other_id, 'in' AS direction, COUNT(*) AS weight
           FROM chat_mentions
           WHERE chat_id = ? AND mentioned_user_id = ? AND mentioning_user_id != ?
           GROUP BY mentioning_user_id
         ) edges
         LEFT JOIN user_stats us ON us.user_id = other_id
         GROUP BY other_id, direction
         ORDER BY weight DESC`,
        [
          match.message.chat.id,
          user.id,
          user.id,
          match.message.chat.id,
          user.id,
          user.id,
        ],
      );
      if (rows.length === 0) {
        const graph = yield* dependencies.database.one(
          "SELECT 1 FROM chat_mentions WHERE chat_id = ? LIMIT 1",
          [match.message.chat.id],
        );
        return yield* answer(
          match.message,
          graph === undefined
            ? "This group has no social graph yet."
            : "You are not in this group's social graph.",
        );
      }
      const outgoing = rows.filter((row) => row["direction"] === "out").slice(0, 3);
      const incoming = rows.filter((row) => row["direction"] === "in").slice(0, 3);
      const render = (heading: string, arrow: string, values: typeof rows) => values.length === 0
        ? ""
        : `\n\n${heading}${values.map((row) => `\n<code>${String(rowNumber(row, "weight")).padStart(6)} ${arrow} ${html.escape(rowString(row, "name"))}</code>`).join("")}`;
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `From the social graph of <b>${html.escape(match.message.chat.title ?? String(match.message.chat.id))}</b>:${render("You have the strongest connections to:", "⟶", outgoing)}${render("You have the strongest connections from:", "←", incoming)}`,
      });
    }),
    usage: "/friends",
  };
}

export function statsCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  return [
    seenCommand(dependencies),
    statsCommand(dependencies, true),
    statsCommand(dependencies, false),
    totalCommand(dependencies, true),
    totalCommand(dependencies, false),
    botStatsCommand(dependencies),
    friendsCommand(dependencies),
  ];
}
