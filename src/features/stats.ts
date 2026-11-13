import {
  answerCallback,
  callbackData,
  callbackTarget,
  editMessageText,
  Effect,
  getMe,
  html,
  Schema,
  type InputRichBlock,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { messageLink } from "../app/links.ts";
import { callbackRoute, ignoreUnchangedMessage } from "../app/callback.ts";
import { replyBlocks, rich } from "../app/rich.ts";

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


const views = ["today", "all", "me", "friends", "bot"] as const;
type View = (typeof views)[number];
const viewLabels: Readonly<Record<View, string>> = {
  all: "All time",
  bot: "Bot",
  friends: "Friends",
  me: "Me",
  today: "Today",
};

const StatsCallback = callbackData("stats", Schema.Struct({ view: Schema.Literals(views) }));

interface StatsChat {
  readonly id: number;
  readonly title?: string | undefined;
}

interface StatsUser {
  readonly id: number;
  readonly name: string;
}

function striped(table: InputRichBlock): InputRichBlock {
  return { ...table, isCompact: true, isStriped: true } as InputRichBlock;
}

function chatTitle(chat: StatsChat): string {
  return chat.title ?? String(chat.id);
}

function keyboard(selected: View | undefined) {
  const button = (view: View) => StatsCallback.button(
    view === selected ? `• ${viewLabels[view]}` : viewLabels[view],
    { view },
  );
  return {
    inlineKeyboard: [
      [button("today"), button("all"), button("me")],
      [button("friends"), button("bot")],
    ],
  };
}

function leaderboard(dependencies: AppDependencies, chat: StatsChat, todayOnly: boolean) {
  return Effect.gen(function* () {
    const time = todayOnly
      ? "AND cs.create_time >= DATE('now', 'localtime') AND cs.create_time < DATE('now', '+1 day', 'localtime')"
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
      [chat.id],
    );
    const heading = rich.heading(`${todayOnly ? "📊 Today" : "📈 All time"} — ${chatTitle(chat)}`);
    const total = rows.reduce((sum, row) => sum + rowNumber(row, "user_count"), 0);
    if (total === 0) return [heading, rich.paragraph("No messages recorded.")];
    const table = rich.table([
      ["Member", "Messages", "Share"],
      ...rows.map((row) => {
        const count = rowNumber(row, "user_count");
        return [rowString(row, "name"), rich.code(String(count)), `${(count / total * 100).toFixed(1)}%`];
      }),
    ], { header: true });
    return [
      heading,
      striped(table),
      rich.footer(["Top 10 total: ", rich.bold(String(total))]),
    ];
  });
}

function friends(dependencies: AppDependencies, chat: StatsChat, user: StatsUser) {
  return Effect.gen(function* () {
    const heading = rich.heading(`🕸️ ${user.name}'s connections — ${chatTitle(chat)}`);
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
      [chat.id, user.id, user.id, chat.id, user.id, user.id],
    );
    if (rows.length === 0) {
      const graph = yield* dependencies.database.one(
        "SELECT 1 FROM chat_mentions WHERE chat_id = ? LIMIT 1",
        [chat.id],
      );
      return [heading, rich.paragraph(graph === undefined
        ? "This group has no social graph yet."
        : `${user.name} is not in this group's social graph.`)];
    }
    const outgoing = rows.filter((row) => row["direction"] === "out").slice(0, 3);
    const incoming = rows.filter((row) => row["direction"] === "in").slice(0, 3);
    const table = rich.table([
      ["Direction", "Member", "Interactions"],
      ...outgoing.map((row) => ["→", rowString(row, "name"), rich.code(String(rowNumber(row, "weight")))]),
      ...incoming.map((row) => ["←", rowString(row, "name"), rich.code(String(rowNumber(row, "weight")))]),
    ], { header: true });
    return [
      heading,
      striped(table),
      rich.footer(`→ ${user.name} mentions or replies to them · ← they mention or reply to ${user.name}`),
    ];
  });
}

function botStats(dependencies: AppDependencies) {
  return Effect.gen(function* () {
    const bot = yield* getMe();
    const totals = yield* dependencies.database.one(
      `SELECT COUNT(DISTINCT user_id) AS users, COUNT(DISTINCT chat_id) AS chats FROM chat_stats`,
    );
    const rows = yield* dependencies.database.all(
      `SELECT command, COUNT(*) AS command_count
       FROM command_stats WHERE create_time >= datetime('now', '-30 days')
       GROUP BY command ORDER BY command_count DESC LIMIT 10`,
    );
    const runs = rows.reduce((sum, row) => sum + rowNumber(row, "command_count"), 0);
    const table = rich.table([
      ["Command", "Runs"],
      ...rows.map((row) => [
        rich.command(`/${rowString(row, "command")}`),
        rich.code(String(rowNumber(row, "command_count"))),
      ]),
    ], { header: true });
    return [
      rich.heading(`🤖 @${bot.username ?? bot.firstName}`),
      rich.paragraph([
        "Users: ", rich.bold(String(totals === undefined ? 0 : rowNumber(totals, "users"))),
        " · Chats: ", rich.bold(String(totals === undefined ? 0 : rowNumber(totals, "chats"))),
      ]),
      rich.heading("Top commands, last 30 days", 4),
      ...(rows.length === 0 ? [rich.paragraph("No commands run.")] : [striped(table)]),
      rich.footer(["Top 10 runs: ", rich.bold(String(runs))]),
    ];
  });
}

function sparkline(values: ReadonlyArray<number>): string {
  const levels = "▁▂▃▄▅▆▇█";
  const maximum = Math.max(...values, 1);
  return values.map((value) => levels[Math.min(
    levels.length - 1,
    Math.floor(value / maximum * (levels.length - 1)),
  )]).join("");
}

function userStats(dependencies: AppDependencies, chat: StatsChat, target: StatsUser) {
  return Effect.gen(function* () {
    const rows = yield* dependencies.database.all(
      `WITH user_daily AS (
         SELECT DATE(create_time, 'localtime') AS value, COUNT(*) AS count
         FROM chat_stats
         WHERE chat_id = ? AND user_id = ?
           AND create_time >= DATE('now', '-6 days', 'localtime')
         GROUP BY value
       ), group_week AS (
         SELECT COUNT(*) AS count FROM chat_stats
         WHERE chat_id = ? AND create_time >= DATE('now', '-6 days', 'localtime')
       ), top_hour AS (
         SELECT strftime('%H', create_time, 'localtime') AS value
         FROM chat_stats WHERE chat_id = ? AND user_id = ?
           AND create_time >= DATE('now', '-30 days', 'localtime')
         GROUP BY value ORDER BY COUNT(*) DESC LIMIT 1
       ), top_day AS (
         SELECT strftime('%w', create_time, 'localtime') AS value
         FROM chat_stats WHERE chat_id = ? AND user_id = ?
           AND create_time >= DATE('now', '-90 days', 'localtime')
         GROUP BY value ORDER BY COUNT(*) DESC LIMIT 1
       ), lifetime AS (
         SELECT COUNT(*) AS count FROM chat_stats WHERE chat_id = ? AND user_id = ?
       )
       SELECT 'daily' AS kind, value, count FROM user_daily
       UNION ALL SELECT 'group', NULL, count FROM group_week
       UNION ALL SELECT 'hour', value, NULL FROM top_hour
       UNION ALL SELECT 'day', value, NULL FROM top_day
       UNION ALL SELECT 'lifetime', NULL, count FROM lifetime`,
      [chat.id, target.id, chat.id, chat.id, target.id, chat.id, target.id, chat.id, target.id],
    );
    const days = Array.from({ length: 7 }, (_, index) => {
      const date = new Date(dependencies.now());
      date.setUTCDate(date.getUTCDate() - (6 - index));
      return date.toISOString().slice(0, 10);
    });
    const daily = new Map(rows.filter((row) => row["kind"] === "daily").map((row) => [
      rowString(row, "value"),
      rowNumber(row, "count"),
    ]));
    const counts = days.map((day) => daily.get(day) ?? 0);
    const week = counts.reduce((sum, count) => sum + count, 0);
    const value = (kind: string, field: string) => {
      const row = rows.find((candidate) => candidate["kind"] === kind);
      return row === undefined || row[field] === null ? undefined : row[field];
    };
    const group = Number(value("group", "count") ?? 0);
    const lifetime = Number(value("lifetime", "count") ?? 0);
    const hour = value("hour", "value");
    const day = value("day", "value");
    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const labels = days.map((date) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en", {
      timeZone: "UTC",
      weekday: "short",
    }));
    const bars = counts.map((count, index) => {
      const width = Math.round(count / Math.max(...counts, 1) * 20);
      return `${labels[index]} | ${"█".repeat(width).padEnd(20)} ${count}`;
    }).join("\n");
    const heading = rich.heading(`👤 ${target.name} — ${chatTitle(chat)}`);
    if (week === 0) return [
      heading,
      rich.paragraph(`No messages in the last 7 days. Lifetime: ${lifetime} messages.`),
    ];
    const table = rich.table([
      ["Metric", "Value"],
      ["Last 7 days", `${week} messages`],
      ["Group share", `${group === 0 ? "0.0" : (week / group * 100).toFixed(1)}%`],
      ["Daily average", (week / 7).toFixed(2)],
      ["Lifetime", `${lifetime} messages`],
      ["Most active hour", hour === undefined ? "—" : `${String(hour).padStart(2, "0")}:00`],
      ["Most active day", day === undefined ? "—" : dayNames[Number(day)] ?? "—"],
    ], { header: true });
    return [
      heading,
      striped(table),
      rich.pre(bars),
      rich.footer(["7-day sparkline: ", rich.code(sparkline(counts))]),
    ];
  });
}

function renderView(
  dependencies: AppDependencies,
  view: View,
  chat: StatsChat,
  user: StatsUser,
): Effect.Effect<ReadonlyArray<InputRichBlock>, unknown, import("telly").Bot> {
  switch (view) {
    case "today":
      return leaderboard(dependencies, chat, true);
    case "all":
      return leaderboard(dependencies, chat, false);
    case "me":
      return userStats(dependencies, chat, user);
    case "friends":
      return friends(dependencies, chat, user);
    case "bot":
      return botStats(dependencies);
  }
}

function statsCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Show chat, member, social and bot stats.",
    example: "/stats @obviyus",
    names: ["stats"],
    run: Effect.fn("stats")(function* (match) {
      const sender = match.message.from;
      if (sender === undefined) return;
      const chat = { id: match.message.chat.id, title: match.message.chat.title };
      const argument = match.args[0]?.toLowerCase();
      const named = argument?.startsWith("@") === true
        ? yield* dependencies.database.one(
            "SELECT user_id, username, first_name FROM user_stats WHERE LOWER(username) = ?",
            [argument.slice(1)],
          )
        : undefined;
      if (argument?.startsWith("@") === true && named === undefined) {
        return yield* answer(match.message, `${match.args[0]} has never been seen in this chat.`);
      }
      const replied = match.message.replyToMessage?.from;
      const target: StatsUser | undefined = named !== undefined
        ? { id: rowNumber(named, "user_id"), name: rowString(named, "username") }
        : replied !== undefined && !replied.isBot
        ? { id: replied.id, name: replied.username ?? replied.firstName }
        : undefined;
      const user = target ?? { id: sender.id, name: sender.username ?? sender.firstName };
      const requested = views.find((view) => view === argument);
      const view: View = requested ?? (target === undefined ? "today" : "me");
      const blocks = yield* renderView(dependencies, view, chat, user);
      return yield* replyBlocks(match.message, blocks, {
        replyMarkup: keyboard(target === undefined || target.id === sender.id ? view : undefined),
      });
    }),
    usage: "/stats [today|all|me|friends|bot|@username]",
  };
}

export function statsCallback(dependencies: AppDependencies) {
  return callbackRoute("stats", StatsCallback, Effect.fn("statsCallback")(function* ({
    callbackQuery,
    data,
  }) {
    const message = callbackQuery.message;
    if (message === undefined) {
      return yield* answerCallback(callbackQuery, { text: "Run /stats again." });
    }
    const from = callbackQuery.from;
    const chat = { id: message.chat.id, title: message.chat.title };
    const blocks = yield* renderView(dependencies, data.view, chat, {
      id: from.id,
      name: from.username ?? from.firstName,
    });
    yield* answerCallback(callbackQuery);
    const target = callbackTarget(callbackQuery);
    if ("ephemeralMessageId" in target) return;
    yield* ignoreUnchangedMessage(editMessageText({
      ...target,
      replyMarkup: keyboard(data.view),
      richMessage: { blocks },
    }));
  }));
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
         JOIN chat_stats cs ON cs.id = (
           SELECT id FROM chat_stats WHERE chat_id = ? AND user_id = us.user_id
           ORDER BY id DESC LIMIT 1
         )
         WHERE LOWER(us.username) = ?
         ORDER BY cs.id DESC LIMIT 1`,
        [match.message.chat.id, username],
      );
      if (row === undefined) {
        return yield* answer(match.message, `@${username} has never been seen in this chat.`);
      }
      const messageId = rowNumber(row, "message_id");
      const url = messageLink(match.message.chat.id, messageId, match.message.chat.username);
      const link = url === undefined ? "" : `\n\n🔗 <a href="${url}">Link</a>`;
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

export function statsCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  return [seenCommand(dependencies), statsCommand(dependencies)];
}
