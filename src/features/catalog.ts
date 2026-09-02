import { XMLParser } from "fast-xml-parser";
import {
  Effect,
  html,
  Schema,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { stripHtml } from "../app/text.ts";

const TextValue = Schema.Union([Schema.String, Schema.Number]);
const Work = Schema.Struct({ best_book: Schema.Struct({ id: TextValue }) });
const SearchXml = Schema.Struct({
  GoodreadsResponse: Schema.Struct({
    search: Schema.Struct({
      results: Schema.Struct({ work: Schema.Union([Work, Schema.Array(Work)]) }),
    }),
  }),
});
const BookXml = Schema.Struct({
  GoodreadsResponse: Schema.Struct({
    book: Schema.Struct({
      authors: Schema.Struct({ author: Schema.Struct({ name: TextValue }) }),
      average_rating: TextValue,
      description: Schema.optionalKey(TextValue),
      isbn13: Schema.optionalKey(TextValue),
      num_pages: Schema.optionalKey(TextValue),
      publication_year: Schema.optionalKey(TextValue),
      title: TextValue,
      url: Schema.optionalKey(TextValue),
    }),
  }),
});

const HltbGame = Schema.Struct({
  comp_main: Schema.optionalKey(Schema.Number),
  comp_plus: Schema.optionalKey(Schema.Number),
  game_alias: Schema.optionalKey(Schema.String),
  game_image: Schema.optionalKey(Schema.String),
  game_name: Schema.String,
});
const HltbResponse = Schema.Struct({ data: Schema.Array(HltbGame) });
const HltbAuth = Schema.Record(
  Schema.String,
  Schema.Union([Schema.String, Schema.Number, Schema.Null]),
);

function string(value: typeof TextValue.Type | undefined, fallback = ""): string {
  return value === undefined ? fallback : String(value);
}

function bookCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    apiKey: "goodreadsApiKey",
    description: "Search for a book on Goodreads.",
    example: "/book The Hitchhiker's Guide to the Galaxy",
    names: ["book"],
    run: Effect.fn("book")(function* (match) {
      if (match.argText.length === 0) return yield* usage(match.message, definition);
      const key = dependencies.config.api.goodreadsApiKey;
      if (key === undefined) return yield* answer(match.message, "❌ Book search is not configured.");
      const parser = new XMLParser();
      const searchUrl = new URL("https://www.goodreads.com/search.xml");
      searchUrl.search = new URLSearchParams({ key, q: match.argText }).toString();
      const search = yield* dependencies.http.text("goodreads", searchUrl).pipe(
        Effect.flatMap((response) => Effect.try({
          try: () => Schema.decodeUnknownSync(SearchXml)(parser.parse(response.data)),
          catch: () => new Error("Invalid Goodreads search response"),
        })),
        Effect.catch(() => Effect.succeed(undefined)),
      );
      const work = search?.GoodreadsResponse.search.results.work;
      const first = Array.isArray(work) ? work[0] : work;
      if (first === undefined) {
        return yield* answer(match.message, "❌ No book found matching your query.");
      }
      const bookUrl = new URL("https://www.goodreads.com/book/show.xml");
      bookUrl.search = new URLSearchParams({ id: String(first.best_book.id), key }).toString();
      const book = yield* dependencies.http.text("goodreads", bookUrl).pipe(
        Effect.flatMap((response) => Effect.try({
          try: () => Schema.decodeUnknownSync(BookXml)(parser.parse(response.data)),
          catch: () => new Error("Invalid Goodreads book response"),
        })),
        Effect.catch(() => Effect.succeed(undefined)),
      );
      if (book === undefined) {
        return yield* answer(match.message, "❌ No book found matching your query.");
      }
      const data = book.GoodreadsResponse.book;
      let description = stripHtml(string(data.description, "No description available."));
      if (description.length > 200) {
        const sentence = description.indexOf(".", 200);
        description = sentence === -1
          ? `${description.slice(0, 200)}...`
          : description.slice(0, sentence + 1);
      }
      const isbn = string(data.isbn13);
      const cover = isbn.length === 0 ? "" : `https://covers.openlibrary.org/b/isbn/${isbn}-L.jpg`;
      const link = string(data.url);
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `<b>${html.escape(string(data.title, "Unknown Title").replace("- ()", ""))}</b> - (${html.escape(string(data.publication_year, "Unknown"))})\n\n<a href="${html.escape(cover)}">&#8205;</a>✏️ ${html.escape(string(data.authors.author.name, "Unknown Author"))}\n⭐ ${html.escape(string(data.average_rating, "0"))}\n📖 ${html.escape(string(data.num_pages, "Unknown"))} pages\n🔗 <a href="${html.escape(link)}">Goodreads</a>\n\n${html.escape(description)}`,
      });
    }),
    usage: "/book [book title]",
  };
  return definition;
}

function similarity(left: string, right: string): number {
  const a = left.toLowerCase().replace(/[^a-z0-9]+/gu, " ").trim();
  const b = right.toLowerCase().replace(/[^a-z0-9]+/gu, " ").trim();
  if (a === b) return 1;
  const grams = (value: string) => {
    const result = new Map<string, number>();
    for (let index = 0; index < value.length - 1; index += 1) {
      const gram = value.slice(index, index + 2);
      result.set(gram, (result.get(gram) ?? 0) + 1);
    }
    return result;
  };
  const leftGrams = grams(a);
  const rightGrams = grams(b);
  let overlap = 0;
  for (const [gram, count] of leftGrams) overlap += Math.min(count, rightGrams.get(gram) ?? 0);
  const total = [...leftGrams.values()].reduce((sum, count) => sum + count, 0) +
    [...rightGrams.values()].reduce((sum, count) => sum + count, 0);
  return total === 0 ? 0 : 2 * overlap / total;
}

function hltbSearch(dependencies: AppDependencies, query: string) {
  const base = "https://howlongtobeat.com/";
  const agent = "Mozilla/5.0 SuperSeriousBot/1.0";
  const headers = { referer: base, "user-agent": agent };
  return dependencies.http.text("howlongtobeat", base, { headers }).pipe(
    Effect.flatMap((homepage) => {
      const scripts = [...homepage.data.matchAll(/<script[^>]+src=["']([^"']*\/_next\/static\/chunks\/[^"']+)["']/giu)]
        .map((match) => new URL(match[1] ?? "", base).toString());
      return Effect.forEach(scripts, (script) => dependencies.http.text(
        "howlongtobeat",
        script,
        { headers },
      ), { concurrency: 4 }).pipe(Effect.map((responses) => responses.map((item) => item.data).join("\n")));
    }),
    Effect.flatMap((scripts) => {
      const endpoint = scripts.match(/fetch\s*\(\s*["'](\/api\/[a-zA-Z0-9_/]+)[^"']*["']\s*,\s*\{[^}]*method:\s*["']POST["']/isu)?.[1] ?? "/api/s/";
      const init = new URL(`${endpoint.replace(/\/$/u, "")}/init`, base);
      init.searchParams.set("t", String(dependencies.now().getTime()));
      return dependencies.http.json("howlongtobeat", init, HltbAuth, { headers }).pipe(
        Effect.map((auth) => ({ auth: auth.data, endpoint })),
      );
    }),
    Effect.flatMap(({ auth, endpoint }) => {
      const token = typeof auth["token"] === "string" ? auth["token"] : undefined;
      const keyEntry = Object.entries(auth).find(([name]) => name.toLowerCase().includes("key"));
      const valueEntry = Object.entries(auth).find(([name]) => name.toLowerCase().includes("val"));
      const authKey = keyEntry?.[1];
      const authValue = valueEntry?.[1];
      const payload: Record<string, unknown> = {
        searchOptions: {
          filter: "",
          games: {
            difficulty: "",
            gameplay: { flow: "", genre: "", perspective: "" },
            modifier: "",
            platform: "",
            rangeCategory: "main",
            rangeTime: { max: 0, min: 0 },
            rangeYear: { max: "", min: "" },
            sortCategory: "popular",
            userId: 0,
          },
          lists: { sortCategory: "follows" },
          randomizer: 0,
          sort: 0,
          users: { sortCategory: "postcount" },
        },
        searchPage: 1,
        searchTerms: query.split(/\s+/u),
        searchType: "games",
        size: 20,
        useCache: true,
      };
      if (typeof authKey === "string") payload[authKey] = authValue;
      return dependencies.http.json(
        "howlongtobeat",
        new URL(endpoint, base),
        HltbResponse,
        {
          body: JSON.stringify(payload),
          headers: {
            ...headers,
            accept: "*/*",
            "content-type": "application/json",
            origin: base,
            ...(token === undefined ? {} : { "x-auth-token": token }),
            ...(typeof authKey === "string" ? { "x-hp-key": authKey } : {}),
            ...(typeof authValue === "string" ? { "x-hp-val": authValue } : {}),
          },
          method: "POST",
        },
      );
    }),
    Effect.map((response) => response.data.data
      .map((game) => ({ game, score: Math.max(
        similarity(query, game.game_name),
        similarity(query, game.game_alias ?? ""),
      ) }))
      .sort((left, right) => right.score - left.score)[0]?.game),
  );
}

function hltbCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Find how long a game takes to beat.",
    example: "/hltb Horizon Zero Dawn",
    names: ["hltb"],
    run: Effect.fn("howLongToBeat")(function* (match) {
      if (match.argText.length === 0) return yield* usage(match.message, definition);
      const game = yield* hltbSearch(dependencies, match.argText).pipe(
        Effect.catch(() => Effect.succeed(undefined)),
      );
      if (game === undefined) return yield* answer(match.message, "No entry found.");
      const seconds = game.comp_main ?? game.comp_plus;
      if (seconds === undefined || seconds < 0) return yield* answer(
        match.message,
        "No hours recorded.",
      );
      const image = game.game_image === undefined
        ? ""
        : `<a href="https://howlongtobeat.com/games/${html.escape(game.game_image)}">&#8205;</a>`;
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `<b>${html.escape(game.game_name)}</b>: ${(seconds / 3_600).toFixed(2)} hours${image}`,
      });
    }),
    usage: "/hltb [game]",
  };
  return definition;
}

export function catalogCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  return [bookCommand(dependencies), hltbCommand(dependencies)];
}
