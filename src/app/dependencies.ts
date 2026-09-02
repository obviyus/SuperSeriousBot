import type { AppConfig } from "./config.ts";
import type { Database } from "./database.ts";
import type { Http } from "./http.ts";

export interface AppDependencies {
  readonly config: AppConfig;
  readonly database: Database;
  readonly http: Http;
  readonly monotonicMilliseconds: () => number;
  readonly now: () => Date;
  readonly random: () => number;
}
