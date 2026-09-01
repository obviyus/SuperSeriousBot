export type Updater = "polling" | "webhook";

export interface ApiConfig {
  readonly cobaltUrl?: string;
  readonly goodreadsApiKey?: string;
  readonly kieApiKey?: string;
  readonly nanoGptApiKey?: string;
  readonly openrouterApiKey?: string;
  readonly waqiApiKey?: string;
  readonly weatherApiKey?: string;
  readonly wolframAppId?: string;
}

export interface AppConfig {
  readonly admins: ReadonlySet<string>;
  readonly api: ApiConfig;
  readonly loggingChannelId?: number;
  readonly port: number;
  readonly quoteChannelId: number;
  readonly stateDirectory: string;
  readonly telegramToken: string;
  readonly tursoAuthToken: string;
  readonly tursoDatabaseUrl: string;
  readonly updater: Updater;
  readonly webhookUrl?: string;
}

type Environment = Readonly<Record<string, string | undefined>>;

function required(environment: Environment, name: string): string {
  const value = environment[name]?.trim();
  if (value === undefined || value.length === 0) throw new Error(`${name} must be set`);
  return value;
}

function optional(environment: Environment, name: string): string | undefined {
  const value = environment[name]?.trim();
  return value === undefined || value.length === 0 ? undefined : value;
}

function integer(environment: Environment, name: string, fallback?: number): number {
  const raw = optional(environment, name);
  if (raw === undefined && fallback !== undefined) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value)) throw new Error(`${name} must be an integer`);
  return value;
}

export function loadConfig(environment: Environment = process.env): AppConfig {
  const updater = optional(environment, "UPDATER") ?? "polling";
  if (updater !== "polling" && updater !== "webhook") {
    throw new Error("UPDATER must be polling or webhook");
  }
  const port = integer(environment, "PORT", 8_443);
  if (port < 1 || port > 65_535) throw new Error("PORT must be from 1 to 65535");
  const webhookUrl = optional(environment, "WEBHOOK_URL");
  if (updater === "webhook" && webhookUrl === undefined) {
    throw new Error("WEBHOOK_URL must be set for webhook mode");
  }
  const cobaltUrl = optional(environment, "COBALT_URL");
  const goodreadsApiKey = optional(environment, "GOODREADS_API_KEY");
  const kieApiKey = optional(environment, "KIE_API_KEY");
  const nanoGptApiKey = optional(environment, "NANO_GPT_API_KEY");
  const openrouterApiKey = optional(environment, "OPENROUTER_API_KEY");
  const waqiApiKey = optional(environment, "WAQI_API_KEY");
  const weatherApiKey = optional(environment, "WEATHERAPI_API_KEY");
  const wolframAppId = optional(environment, "WOLFRAM_APP_ID");
  const loggingChannelId = optional(environment, "LOGGING_CHANNEL_ID");
  return {
    admins: new Set((optional(environment, "ADMINS") ?? "").split(/\s+/u).filter(Boolean)),
    api: {
      ...(cobaltUrl === undefined ? {} : { cobaltUrl }),
      ...(goodreadsApiKey === undefined ? {} : { goodreadsApiKey }),
      ...(kieApiKey === undefined ? {} : { kieApiKey }),
      ...(nanoGptApiKey === undefined ? {} : { nanoGptApiKey }),
      ...(openrouterApiKey === undefined ? {} : { openrouterApiKey }),
      ...(waqiApiKey === undefined ? {} : { waqiApiKey }),
      ...(weatherApiKey === undefined ? {} : { weatherApiKey }),
      ...(wolframAppId === undefined ? {} : { wolframAppId }),
    },
    ...(loggingChannelId === undefined
      ? {}
      : { loggingChannelId: integer(environment, "LOGGING_CHANNEL_ID") }),
    port,
    quoteChannelId: integer(environment, "QUOTE_CHANNEL_ID"),
    stateDirectory: optional(environment, "TELLY_STATE_DIRECTORY") ?? "./db",
    telegramToken: required(environment, "TELEGRAM_TOKEN"),
    tursoAuthToken: required(environment, "TURSO_AUTH_TOKEN"),
    tursoDatabaseUrl: required(environment, "TURSO_DATABASE_URL"),
    updater,
    ...(webhookUrl === undefined ? {} : { webhookUrl }),
  };
}
