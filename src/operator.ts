import { Effect } from "telly";

import { loadConfig } from "./app/config.ts";
import { Database } from "./app/database.ts";
import type { AppDependencies } from "./app/dependencies.ts";
import { Http } from "./app/http.ts";
import { initializeDatabase } from "./app/schema.ts";
import { createSuperSeriousBot } from "./bot.ts";

interface UsageFilters {
  readonly command?: string;
  readonly days: number;
  readonly limit: number;
  readonly status?: "blocked" | "completed" | "failed";
}

function isUsageStatus(value: string): value is NonNullable<UsageFilters["status"]> {
  return value === "blocked" || value === "completed" || value === "failed";
}

function plainRow(row: import("@libsql/client").Row): Readonly<Record<string, unknown>> {
  return Object.fromEntries(Object.entries(row).filter(([key]) => !/^\d+$/u.test(key)));
}

export function commandUsageReport(database: Database, filters: UsageFilters) {
  const conditions = ["create_time >= datetime('now', ?)"];
  const parameters: Array<string | number> = [`-${filters.days} days`];
  if (filters.command !== undefined) {
    conditions.push("command = ?");
    parameters.push(filters.command.replace(/^\//u, "").toLowerCase());
  }
  if (filters.status !== undefined) {
    conditions.push("status = ?");
    parameters.push(filters.status);
  }
  const where = conditions.join(" AND ");
  return Effect.all({
    byCommand: database.all(
      `SELECT command, COUNT(*) AS count FROM command_stats
       WHERE ${where} GROUP BY command ORDER BY count DESC, command`,
      parameters,
    ),
    events: database.all(
      `SELECT id, create_time, command, input_text, status, duration_ms,
              username, user_id, chat_id, message_id, error_type, error_message,
              error_traceback
       FROM command_stats WHERE ${where} ORDER BY id DESC LIMIT ?`,
      [...parameters, filters.limit],
    ),
    summary: database.one(
      `SELECT COUNT(*) AS total,
              COALESCE(SUM(status = 'completed'), 0) AS completed,
              COALESCE(SUM(status = 'blocked'), 0) AS blocked,
              COALESCE(SUM(status = 'failed'), 0) AS failed,
              CAST(AVG(duration_ms) AS INTEGER) AS average_duration_ms
       FROM command_stats WHERE ${where}`,
      parameters,
    ),
  }).pipe(Effect.map(({ byCommand, events, summary }) => ({
    byCommand: byCommand.map(plainRow),
    events: events.map(plainRow),
    filters,
    summary: summary === undefined ? {} : plainRow(summary),
  })));
}

function option(args: ReadonlyArray<string>, name: string): string | undefined {
  const index = args.indexOf(name);
  return index === -1 ? undefined : args[index + 1];
}

function positiveInteger(value: string | undefined, fallback: number, name: string): number {
  if (value === undefined) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1) throw new Error(`${name} must be a positive integer`);
  return parsed;
}

function chatIds(args: ReadonlyArray<string>): ReadonlyArray<number> | undefined {
  const values = args.flatMap((argument, index) => argument === "--chat-id"
    ? [args[index + 1]]
    : []).filter((value): value is string => value !== undefined);
  if (values.length === 0) return undefined;
  return values.map((value) => {
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new Error("--chat-id must be an integer");
    return parsed;
  });
}

async function main(): Promise<void> {
  const [operation, ...args] = Bun.argv.slice(2);
  if (!new Set(["usage", "search-index", "search-memory"]).has(operation ?? "")) {
    throw new Error("Usage: bun run operator <usage|search-index|search-memory> [options]");
  }
  const config = loadConfig();
  const database = Database.open(config);
  try {
    await Effect.runPromise(initializeDatabase(database));
    if (operation === "usage") {
      const command = option(args, "--command");
      const status = option(args, "--status");
      if (status !== undefined && !isUsageStatus(status)) {
        throw new Error("--status must be blocked, completed, or failed");
      }
      const report = await Effect.runPromise(commandUsageReport(database, {
        ...(command === undefined ? {} : { command }),
        days: positiveInteger(option(args, "--days"), 7, "--days"),
        limit: positiveInteger(option(args, "--limit"), 100, "--limit"),
        ...(status === undefined ? {} : { status }),
      }));
      console.log(JSON.stringify(report, null, 2));
      return;
    }
    const dependencies: AppDependencies = {
      config,
      database,
      http: new Http(),
      monotonicMilliseconds: performance.now.bind(performance),
      now: () => new Date(),
      random: Math.random,
    };
    const search = createSuperSeriousBot(dependencies).workers.search;
    await Effect.runPromise(operation === "search-index"
      ? search.index(chatIds(args))
      : search.memory(chatIds(args)));
  } finally {
    database.close();
  }
}

if (import.meta.main) {
  main().catch((error: unknown) => {
    console.error(error);
    process.exitCode = 1;
  });
}
