import { Database } from "bun:sqlite";

// Runs one agent-written query against a chat's read-only search copy.
// A worker keeps a slow query off the bot's event loop; the caller
// terminates it on timeout.

declare const self: Worker;

interface Request {
  readonly maxRows: number;
  readonly path: string;
  readonly sql: string;
  readonly textLimit: number;
}

self.onmessage = (event: MessageEvent<Request>) => {
  const { maxRows, path, sql, textLimit } = event.data;
  let database: Database | undefined;
  try {
    database = new Database(path, { readonly: true });
    database.exec("PRAGMA query_only = ON");
    const statement = database.query(sql);
    const rows: Array<Record<string, unknown>> = [];
    let truncated = false;
    for (const row of statement.iterate() as Iterable<Record<string, unknown>>) {
      if (rows.length === maxRows) {
        truncated = true;
        break;
      }
      rows.push(Object.fromEntries(Object.entries(row).map(([key, value]) => [
        key,
        typeof value === "string" && value.length > textLimit ? `${value.slice(0, textLimit)}…` : value,
      ])));
    }
    postMessage({ rows, truncated });
  } catch (error) {
    postMessage({ error: error instanceof Error ? error.message : String(error) });
  } finally {
    database?.close();
  }
};
