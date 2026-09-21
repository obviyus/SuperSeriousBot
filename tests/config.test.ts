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
    NANO_GPT_API_KEY: "nano-test",
    BASED_BASE_URL: " https://local-ai.test/v1 ",
    BASED_MODEL: " local-model ",
    OPENROUTER_API_KEY: " openrouter-test ",
    OPENROUTER_BASE_URL: " http://127.0.0.1:9100 ",
    TELEGRAM_API_ROOT: " http://127.0.0.1:9000 ",
  });

  expect(config.api.based).not.toHaveProperty("apiKey");
  expect(config).toMatchObject({
    admins: new Set(["1", "2"]),
    api: {
      based: { provider: "local", baseUrl: "https://local-ai.test/v1", model: "local-model" },
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


test("local AI stays disabled without an endpoint and requires a served model ID", () => {
  expect(loadConfig(required).api.based).toBeUndefined();
  expect(() => loadConfig({ ...required, BASED_BASE_URL: "https://local-ai.test/v1" }))
    .toThrow("BASED_MODEL must be set");
});


test("based selects NanoGPT with its existing key and a fixed provider endpoint", () => {
  const config = loadConfig({
    ...required,
    BASED_PROVIDER: "nanogpt",
    BASED_BASE_URL: "https://old-local.test/v1",
    BASED_MODEL: "test/hosted-model",
    NANO_GPT_API_KEY: " nano-test ",
    OPENROUTER_API_KEY: "openrouter-test",
  });
  expect(config.api.based).toEqual({
    provider: "nanogpt",
    baseUrl: "https://nano-gpt.com/api/v1",
    model: "test/hosted-model",
    apiKey: "nano-test",
  });
  expect(() => loadConfig({ ...required, BASED_PROVIDER: "nanogpt", BASED_MODEL: "test/hosted-model" }))
    .toThrow("NANO_GPT_API_KEY must be set");
  expect(() => loadConfig({ ...required, BASED_PROVIDER: "unknown" }))
    .toThrow("BASED_PROVIDER must be local or nanogpt");
});
