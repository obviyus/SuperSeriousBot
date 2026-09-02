import {
  Effect,
  Schema,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowNumber } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { replyBlocks, rich } from "../app/rich.ts";
import { truncate } from "../app/text.ts";

const DictionaryResponse = Schema.Array(Schema.Struct({
  meanings: Schema.optionalKey(Schema.Array(Schema.Struct({
    definitions: Schema.optionalKey(Schema.Array(Schema.Struct({
      definition: Schema.String,
      synonyms: Schema.optionalKey(Schema.Array(Schema.String)),
    }))),
    partOfSpeech: Schema.optionalKey(Schema.String),
  }))),
  phonetics: Schema.optionalKey(Schema.Array(Schema.Struct({
    text: Schema.optionalKey(Schema.String),
  }))),
  word: Schema.String,
}));

const UrbanEntry = Schema.Struct({
  date: Schema.optionalKey(Schema.String),
  definition: Schema.String,
  example: Schema.String,
  permalink: Schema.String,
  thumbs_up: Schema.Number,
  word: Schema.String,
});
const UrbanResponse = Schema.Struct({
  list: Schema.optionalKey(Schema.Array(UrbanEntry)),
});

const WeatherResponse = Schema.Struct({
  current: Schema.Struct({
    air_quality: Schema.optionalKey(Schema.Struct({
      pm10: Schema.optionalKey(Schema.Number),
      pm2_5: Schema.optionalKey(Schema.Number),
    })),
    condition: Schema.Struct({ text: Schema.String }),
    feelslike_c: Schema.Number,
    humidity: Schema.Number,
    temp_c: Schema.Number,
    wind_dir: Schema.String,
    wind_kph: Schema.Number,
  }),
  location: Schema.Struct({
    country: Schema.String,
    lat: Schema.Number,
    localtime: Schema.optionalKey(Schema.String),
    lon: Schema.Number,
    name: Schema.String,
    region: Schema.String,
  }),
});
const AqiResponse = Schema.Struct({
  data: Schema.optionalKey(Schema.Struct({
    aqi: Schema.optionalKey(Schema.Union([Schema.Number, Schema.String])),
  })),
  status: Schema.String,
});
const TranslationResponse = Schema.Array(Schema.Unknown);

function definitionCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Define a word.",
    example: "/define posthumous",
    names: ["define", "d"],
    run: Effect.fn("define")(function* (match) {
      if (match.argText.length === 0) return yield* usage(match.message, definition);
      const response = yield* dependencies.http.json(
        "dictionaryapi",
        `https://api.dictionaryapi.dev/api/v2/entries/en_US/${encodeURIComponent(match.argText)}`,
        DictionaryResponse,
      ).pipe(Effect.catch(() => Effect.succeed(undefined)));
      const entry = response?.status === 200 ? response.data[0] : undefined;
      if (entry === undefined) return yield* answer(match.message, "Word not found.");
      const phonetic = entry.phonetics?.find((item) => item.text !== undefined)?.text;
      const meaning = entry.meanings?.[0];
      const firstDefinition = meaning?.definitions?.[0];
      const blocks = [rich.heading(`📖 ${entry.word}`)];
      if (phonetic !== undefined) blocks.push(rich.paragraph(["🗣️ ", rich.code(phonetic)]));
      if (meaning?.partOfSpeech !== undefined && firstDefinition !== undefined) {
        blocks.push(rich.heading(meaning.partOfSpeech, 4));
        blocks.push(rich.paragraph(firstDefinition.definition));
        const synonyms = firstDefinition.synonyms?.slice(0, 2) ?? [];
        if (synonyms.length > 0) {
          blocks.push({
            blocks: [rich.list(synonyms)],
            summary: "Synonyms",
            type: "details",
          });
        }
      }
      return yield* replyBlocks(match.message, blocks);
    }),
    usage: "/define [word]",
  };
  return definition;
}

function urbanDictionaryCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Search Urban Dictionary or get the Word of the Day.",
    example: "/ud racism or /ud",
    names: ["ud"],
    run: Effect.fn("urbanDictionary")(function* (match) {
      const wordOfTheDay = match.argText.length === 0;
      const url = new URL(wordOfTheDay
        ? "https://api.urbandictionary.com/v0/words_of_the_day"
        : "https://api.urbandictionary.com/v0/define");
      if (!wordOfTheDay) url.searchParams.set("term", match.argText.toLowerCase());
      const response = yield* dependencies.http.json(
        "urban-dictionary",
        url,
        UrbanResponse,
        { headers: { accept: "application/json", "user-agent": "SuperSeriousBot" } },
      ).pipe(Effect.catch(() => Effect.succeed(undefined)));
      const entries = response?.status === 200 ? response.data.list ?? [] : [];
      const entry = wordOfTheDay
        ? entries[0]
        : entries.reduce<(typeof entries)[number] | undefined>(
            (best, item) => best === undefined || item.thumbs_up > best.thumbs_up ? item : best,
            undefined,
          );
      if (entry === undefined) return yield* answer(match.message, "No results found.");
      const permalink = URL.canParse(entry.permalink) && ["http:", "https:"].includes(
        new URL(entry.permalink).protocol,
      ) ? entry.permalink : "";
      const title = permalink.length === 0
        ? entry.word
        : rich.link(entry.word, permalink);
      return yield* replyBlocks(match.message, [
        rich.heading(wordOfTheDay ? ["📅 Word of the day — ", title] : ["📚 ", title]),
        rich.paragraph(truncate(entry.definition, 1_000)),
        {
          blocks: [rich.paragraph(truncate(entry.example, 1_000))],
          type: "blockquote",
        },
        rich.footer([
          `👍 ${entry.thumbs_up}`,
          ...(wordOfTheDay ? [` · ${entry.date ?? "Today"}`] : []),
        ]),
      ]);
    }),
    usage: "/ud [word] or /ud",
  };
}

function calculationCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    apiKey: "wolframAppId",
    description: "Answer a calculation or facts query.",
    example: "/calc 300th digit of pi",
    names: ["calc"],
    run: Effect.fn("calculate")(function* (match) {
      if (match.argText.length === 0) return yield* usage(match.message, definition);
      if (match.argText.length > 1_000) return yield* answer(match.message, "❌ Invalid query");
      const appId = dependencies.config.api.wolframAppId;
      if (appId === undefined) return yield* answer(
        match.message,
        "❌ Calculation service is not configured.",
      );
      const url = new URL("https://api.wolframalpha.com/v1/result");
      url.search = new URLSearchParams({ appid: appId, i: match.argText }).toString();
      const response = yield* dependencies.http.text("wolfram", url).pipe(
        Effect.catch(() => Effect.succeed(undefined)),
      );
      const text = response === undefined
        ? "❌ Connection error"
        : response.status === 200
        ? response.data
        : response.status === 501
        ? "❌ I couldn't understand that query."
        : response.status === 403
        ? "❌ Calculation service is not configured."
        : "❌ Calculation service is unavailable.";
      return yield* answer(match.message, text);
    }),
    usage: "/calc [query]",
  };
  return definition;
}

function translationText(match: Parameters<CommandDefinition["run"]>[0]) {
  const replied = match.message.replyToMessage;
  if (replied !== undefined) {
    const text = replied.text ?? replied.caption;
    return text === undefined ? undefined : {
      target: match.args[0] ?? "en",
      text,
    };
  }
  const separator = match.args.indexOf("-");
  if (separator === -1) {
    return match.argText.length === 0 ? undefined : { target: "en", text: match.argText };
  }
  const text = match.args.slice(separator + 1).join(" ");
  return text.length === 0 ? undefined : { target: match.args[0] ?? "en", text };
}

function parseTranslation(data: ReadonlyArray<unknown>): string | undefined {
  const segments = data[0];
  if (!Array.isArray(segments)) return undefined;
  const translated = segments.flatMap((segment) =>
    Array.isArray(segment) && typeof segment[0] === "string" ? [segment[0]] : []
  ).join("");
  return translated.length === 0 ? undefined : translated;
}

function translationCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Translate a message or text to the requested language.",
    example: "/tl fr - Good morning!",
    names: ["tl"],
    run: Effect.fn("translate")(function* (match) {
      const input = translationText(match);
      if (input === undefined) return yield* usage(match.message, definition);
      const url = new URL("https://translate.googleapis.com/translate_a/single");
      url.search = new URLSearchParams({
        client: "gtx",
        dt: "t",
        q: input.text,
        sl: "auto",
        tl: input.target,
      }).toString();
      const response = yield* dependencies.http.json(
        "google-translate",
        url,
        TranslationResponse,
      ).pipe(Effect.catch(() => Effect.succeed(undefined)));
      const translated = response === undefined ? undefined : parseTranslation(response.data);
      return yield* answer(
        match.message,
        translated ?? `Invalid target language: ${input.target}`,
      );
    }),
    usage: "/tl [language] - [content]",
  };
  return definition;
}

function pollutant(value: number | undefined): string {
  return value === undefined ? "Unavailable" : `${value.toFixed(1)} µg/m³`;
}

function weatherCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Get the weather for a location and save the last location.",
    example: "/w Berlin",
    names: ["weather", "w"],
    run: Effect.fn("weather")(function* (match) {
      const user = match.message.from;
      if (user === undefined) return;
      let query = match.argText;
      if (query.length === 0) {
        const cached = yield* dependencies.database.one(
          "SELECT latitude, longitude FROM weather_cache WHERE user_id = ?",
          [user.id],
        );
        if (cached === undefined) return yield* usage(match.message, definition);
        query = `${rowNumber(cached, "latitude")},${rowNumber(cached, "longitude")}`;
      }
      const weatherApiKey = dependencies.config.api.weatherApiKey;
      const waqiApiKey = dependencies.config.api.waqiApiKey;
      if (weatherApiKey === undefined || waqiApiKey === undefined) {
        return yield* answer(match.message, "Could not fetch weather data right now.");
      }
      const weatherUrl = new URL("https://api.weatherapi.com/v1/current.json");
      weatherUrl.search = new URLSearchParams({
        aqi: "yes",
        key: weatherApiKey,
        q: query,
      }).toString();
      const weather = yield* dependencies.http.json(
        "weatherapi",
        weatherUrl,
        WeatherResponse,
      ).pipe(Effect.catch(() => Effect.succeed(undefined)));
      if (weather === undefined || weather.status !== 200) {
        return yield* answer(match.message, "Could not fetch weather data right now.");
      }
      const { current, location } = weather.data;
      const aqiUrl = new URL(`https://api.waqi.info/feed/geo:${location.lat};${location.lon}/`);
      aqiUrl.searchParams.set("token", waqiApiKey);
      const aqi = yield* dependencies.http.json("waqi", aqiUrl, AqiResponse).pipe(
        Effect.catch(() => Effect.succeed(undefined)),
      );
      if (aqi?.data.status !== "ok") {
        return yield* answer(match.message, "Could not fetch weather data right now.");
      }
      const address = [location.name, location.region, location.country].filter(Boolean).join(", ");
      if (match.argText.length > 0) {
        yield* dependencies.database.execute(
          `INSERT INTO weather_cache (user_id, latitude, longitude, address, update_time)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id) DO UPDATE SET
             latitude = excluded.latitude,
             longitude = excluded.longitude,
             address = excluded.address,
             update_time = CURRENT_TIMESTAMP`,
          [user.id, location.lat, location.lon, address],
        );
      }
      const aqiValue = aqi.data.data?.aqi;
      const renderedAqi = aqiValue === undefined || aqiValue === "-"
        ? "Unavailable"
        : String(Math.trunc(Number(aqiValue)));
      const table = rich.table([
        ["Measure", "Value"],
        ["🌡️ Temperature", `${current.temp_c.toFixed(1)} °C`],
        ["🫠 Feels like", `${current.feelslike_c.toFixed(1)} °C`],
        ["💦 Humidity", `${current.humidity}%`],
        ["💨 Wind", `${current.wind_kph.toFixed(1)} km/h ${current.wind_dir}`],
        ["🛰 AQI", renderedAqi],
        ["🌫 PM2.5", pollutant(current.air_quality?.pm2_5)],
        ["🏭 PM10", pollutant(current.air_quality?.pm10)],
      ], { header: true });
      return yield* replyBlocks(match.message, [
        rich.heading(`🌦️ ${address}`),
        rich.paragraph(current.condition.text),
        { ...table, isCompact: true, isStriped: true },
      ]);
    }),
    usage: "/w [location]",
  };
  return definition;
}

export function informationCommands(
  dependencies: AppDependencies,
): ReadonlyArray<CommandDefinition> {
  return [
    definitionCommand(dependencies),
    urbanDictionaryCommand(dependencies),
    calculationCommand(dependencies),
    translationCommand(dependencies),
    weatherCommand(dependencies),
  ];
}
