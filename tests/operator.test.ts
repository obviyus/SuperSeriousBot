import { expect, test } from "bun:test";
import { Effect } from "telly";

import type { Fetch } from "../src/app/http.ts";
import { commandUsageReport } from "../src/operator.ts";
import { fixture } from "./harness.ts";

const offline: Fetch = async () => new Response("{}");

test("operator usage report filters command failures", async () => {
  const { app, database } = await fixture(offline);
  await Effect.runPromise(database.batch([
    {
      args: ["ask", 1, "failed", 90, "provider failed"],
      sql: `INSERT INTO command_stats (
        command, user_id, status, duration_ms, error_message
      ) VALUES (?, ?, ?, ?, ?)`,
    },
    {
      args: ["ping", 2, "completed", 10],
      sql: `INSERT INTO command_stats (
        command, user_id, status, duration_ms
      ) VALUES (?, ?, ?, ?)`,
    },
  ]));

  const report = await Effect.runPromise(commandUsageReport(database, {
    command: "/ask",
    days: 7,
    limit: 10,
    status: "failed",
  }));

  await app.close();
  database.close();
  expect(report.summary).toMatchObject({ average_duration_ms: 90, failed: 1, total: 1 });
  expect(report.byCommand).toEqual([expect.objectContaining({ command: "ask", count: 1 })]);
  expect(report.events).toEqual([expect.objectContaining({ error_message: "provider failed" })]);
});
