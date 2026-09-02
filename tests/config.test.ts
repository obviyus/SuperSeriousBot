import { expect, test } from "bun:test";

import { loadConfig } from "../src/app/config.ts";

const required = {
  QUOTE_CHANNEL_ID: "-1007",
  TELEGRAM_TOKEN: "123456:test",
  TURSO_AUTH_TOKEN: "database-test",
  TURSO_DATABASE_URL: "libsql://database.test",
};

test("config loads polling defaults and trims optional values", () => {
  const config = loadConfig({
    ...required,
    ADMINS: " 1   2 ",
    OPENROUTER_API_KEY: " openrouter-test ",
    OPENROUTER_BASE_URL: " http://127.0.0.1:9100 ",
    TELEGRAM_API_ROOT: " http://127.0.0.1:9000 ",
  });

  expect(config).toMatchObject({
    admins: new Set(["1", "2"]),
    api: {
      openrouterApiKey: "openrouter-test",
      openrouterBaseUrl: "http://127.0.0.1:9100",
    },
    port: 8_443,
    telegramApiRoot: "http://127.0.0.1:9000",
    updater: "polling",
  });
});

test("config rejects webhook mode without a public URL", () => {
  expect(() => loadConfig({ ...required, UPDATER: "webhook" })).toThrow(
    "WEBHOOK_URL must be set for webhook mode",
  );
});

test("config rejects invalid updater and port values", () => {
  expect(() => loadConfig({ ...required, UPDATER: "socket" })).toThrow(
    "UPDATER must be polling or webhook",
  );
  expect(() => loadConfig({ ...required, PORT: "70000" })).toThrow(
    "PORT must be from 1 to 65535",
  );
});
