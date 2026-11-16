import { Database } from "bun:sqlite";

// Runs one agent-written query against a chat's read-only search copy.
// A worker keeps a slow query off the bot's event loop.

declare const self: Worker;

interface Request {
  readonly path: string;
  readonly sql: string;
}

self.onmessage = (event: MessageEvent<Request>) => {
  const { path, sql } = event.data;
  let database: Database | undefined;
  try {
    database = new Database(path, { readonly: true });
    postMessage({ rows: database.query(sql).all() });
  } catch (error) {
    postMessage({ error: error instanceof Error ? error.message : String(error) });
  } finally {
    database?.close();
  }
};
