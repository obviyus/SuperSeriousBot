import {
  createClient,
  type Client,
  type InArgs,
  type InStatement,
  type ResultSet,
  type Row,
} from "@libsql/client";
import { Effect, Schema } from "telly";

import type { AppConfig } from "./config.ts";

export class DatabaseError extends Schema.TaggedError<DatabaseError>()("DatabaseError", {
  description: Schema.String,
  operation: Schema.String,
}) {}

function description(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export class Database {
  static open(config: Pick<AppConfig, "tursoAuthToken" | "tursoDatabaseUrl">): Database {
    const url = config.tursoDatabaseUrl === ":memory:"
      ? "file::memory:"
      : config.tursoDatabaseUrl;
    return new Database(createClient({
      authToken: config.tursoAuthToken,
      intMode: "number",
      url,
    }));
  }

  constructor(readonly client: Client) {}

  execute(sql: string, args: InArgs = []): Effect.Effect<ResultSet, DatabaseError> {
    return Effect.tryPromise({
      try: () => this.client.execute(sql, args),
      catch: (error) => new DatabaseError({ description: description(error), operation: "execute" }),
    });
  }

  all(sql: string, args: InArgs = []): Effect.Effect<ReadonlyArray<Row>, DatabaseError> {
    return this.execute(sql, args).pipe(Effect.map((result) => result.rows));
  }

  one(sql: string, args: InArgs = []): Effect.Effect<Row | undefined, DatabaseError> {
    return this.all(sql, args).pipe(Effect.map((rows) => rows[0]));
  }

  batch(statements: ReadonlyArray<InStatement>): Effect.Effect<ReadonlyArray<ResultSet>, DatabaseError> {
    return Effect.tryPromise({
      try: () => this.client.batch([...statements], "write"),
      catch: (error) => new DatabaseError({ description: description(error), operation: "batch" }),
    });
  }

  close(): void {
    this.client.close();
  }
}

export function rowNumber(row: Row, field: string): number {
  const value = row[field];
  if (typeof value === "number") return value;
  if (typeof value === "bigint") return Number(value);
  throw new TypeError(`Database field ${field} is not a number`);
}

export function rowString(row: Row, field: string): string {
  const value = row[field];
  if (typeof value !== "string") throw new TypeError(`Database field ${field} is not text`);
  return value;
}
