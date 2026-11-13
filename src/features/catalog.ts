import { XMLParser } from "fast-xml-parser";
import {
  Effect,
  html,
  replyTo,
  respondTo,
  Schema,
  sendPhoto,
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
const Author = Schema.Struct({
  name: TextValue,
  role: Schema.optionalKey(TextValue),
});
const BookXml = Schema.Struct({
  GoodreadsResponse: Schema.Struct({
    book: Schema.Struct({
      authors: Schema.Struct({ author: Schema.Union([Author, Schema.Array(Author)]) }),
      average_rating: TextValue,
      description: Schema.optionalKey(TextValue),
      image_url: Schema.optionalKey(TextValue),
      num_pages: Schema.optionalKey(TextValue),
      publication_year: Schema.optionalKey(TextValue),
      title: TextValue,
      url: Schema.optionalKey(TextValue),
      work: Schema.optionalKey(Schema.Struct({
        original_publication_year: Schema.optionalKey(TextValue),
        ratings_count: Schema.optionalKey(TextValue),
      })),
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

const captionLimit = 1_024;
const coverBytes = 10 * 1_024 * 1_024;
// Goodreads shelves mix genres with reading-status and ownership labels.
const statusShelf = /read|tbr|own|favou?rite|dnf|did-not|wish|kindle|e-?books?|audio|library|default|club|series|buy|borrow|shelf|list|^\d|my-|maybe|someday|have|bought|gave-up|abandon|^to-|^i-/u;

interface Book {
  readonly authors: ReadonlyArray<string>;
  readonly cover?: string;
  readonly description: string;
  readonly genres: ReadonlyArray<string>;
  readonly pages?: string;
  readonly rating: string;
  readonly ratings?: number;
  readonly series?: string;
  readonly title: string;
  readonly url?: string;
  readonly year?: string;
}

function present(value: typeof TextValue.Type | undefined): string | undefined {
  const text = value === undefined ? "" : String(value).trim();
  return text.length === 0 ? undefined : text;
}

const shelfAliases: Readonly<Record<string, string>> = {
  "non-fiction": "nonfiction",
  "sci-fi": "science-fiction",
  "scifi": "science-fiction",
  "ya": "young-adult",
};

export function bookGenres(xml: string): ReadonlyArray<string> {
  const names = [...xml.matchAll(/<shelf name="([^"]+)"/gu)]
    .map((match) => match[1] ?? "")
    .filter((name) => name.length > 0 && !statusShelf.test(name))
    .map((name) => shelfAliases[name] ?? name);
  return [...new Set(names)]
    .slice(0, 3)
    .map((name) => name.split("-").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" "));
}

export function parseBook(xml: string): Book {
  const data = Schema.decodeUnknownSync(BookXml)(new XMLParser().parse(xml)).GoodreadsResponse.book;
  const authors = [data.authors.author].flat();
  const primary = authors.filter((author) => present(author.role) === undefined);
  const title = present(data.title) ?? "Unknown title";
  // Goodreads appends the series to the title: "Dune (Dune, #1)".
  const parts = title.match(/^(.+?)\s*\(([^()]+?),?\s*#\s*([\d.]+(?:-[\d.]+)?)\)$/u);
  const bare = parts?.[1] ?? title;
  const series = parts === null ? undefined : `${parts[2]} #${parts[3]}`;
  const image = present(data.image_url);
  const cover = image === undefined || image.includes("nophoto")
    ? undefined
    : image.replace(/\._S[XY]\d+_(?=\.\w+$)/u, "");
  const ratings = Number(present(data.work?.ratings_count));
  const pages = present(data.num_pages);
  const url = present(data.url);
  const year = present(data.work?.original_publication_year) ?? present(data.publication_year);
  return {
    authors: (primary.length === 0 ? authors : primary).map((author) => String(author.name)),
    description: stripHtml(present(data.description) ?? "").replace(/\s+/gu, " ").trim(),
    genres: bookGenres(xml),
    rating: present(data.average_rating) ?? "0",
    title: bare,
    ...(cover === undefined ? {} : { cover }),
    ...(pages === undefined ? {} : { pages }),
    ...(Number.isFinite(ratings) && ratings > 0 ? { ratings } : {}),
    ...(series === undefined || series.length === 0 ? {} : { series }),
    ...(url === undefined ? {} : { url }),
    ...(year === undefined ? {} : { year }),
  };
}

function compact(count: number): string {
  return new Intl.NumberFormat("en", { maximumFractionDigits: 1, notation: "compact" }).format(count);
}

function trimToSentence(text: string, limit: number): string {
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const sentence = cut.lastIndexOf(". ");
  return sentence > limit / 2 ? cut.slice(0, sentence + 1) : `${cut.slice(0, cut.lastIndexOf(" "))}…`;
}

export function bookCaption(book: Book): string {
  const byline = [book.authors.slice(0, 3).join(", "), book.year].filter(Boolean).join(" · ");
  const stats = [
    book.ratings === undefined
      ? "⭐ No ratings yet"
      : `⭐ ${book.rating} (${compact(book.ratings)} ratings)`,
    book.pages === undefined ? undefined : `${book.pages} pages`,
  ].filter(Boolean).join(" · ");
  const head = [
    `<b>${html.escape(book.title)}</b>`,
    ...(book.series === undefined ? [] : [`<i>${html.escape(book.series)}</i>`]),
    html.escape(byline),
    "",
    html.escape(stats),
    ...(book.genres.length === 0 ? [] : [`🏷 ${html.escape(book.genres.join(" · "))}`]),
  ].join("\n");
  if (book.description.length === 0) return head;
  const room = captionLimit - head.length - "\n\n".length - 64;
  if (room < 80) return head;
  return `${head}\n\n<blockquote expandable>${html.escape(trimToSentence(book.description, room))}</blockquote>`;
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
      const searchUrl = new URL("https://www.goodreads.com/search.xml");
      searchUrl.search = new URLSearchParams({ key, q: match.argText }).toString();
      const search = yield* dependencies.http.text("goodreads", searchUrl).pipe(
        Effect.flatMap((response) => Effect.try({
          try: () => Schema.decodeUnknownSync(SearchXml)(new XMLParser().parse(response.data)),
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
          try: () => parseBook(response.data),
          catch: (error) => new Error(`Invalid Goodreads book response: ${String(error)}`),
        })),
        Effect.tapError((error) => Effect.logWarning("Goodreads book lookup failed").pipe(
          Effect.annotateLogs({ error: error.message }),
        )),
        Effect.catch(() => Effect.succeed(undefined)),
      );
      if (book === undefined) {
        return yield* answer(match.message, "❌ Goodreads returned a book I couldn't read. Try a more specific title.");
      }
      const caption = bookCaption(book);
      const replyMarkup = book.url === undefined
        ? undefined
        : { inlineKeyboard: [[{ text: "Open on Goodreads", url: book.url }]] };
      const markup = replyMarkup === undefined ? {} : { replyMarkup };
      const cover = book.cover === undefined
        ? undefined
        : yield* dependencies.http.bytes("goodreads", book.cover, coverBytes).pipe(
            Effect.map((response) => response.status === 200 ? response : undefined),
            Effect.catch(() => Effect.succeed(undefined)),
          );
      if (cover !== undefined) {
        const sent = yield* Effect.result(sendPhoto({
          ...(match.message.chat.type === "private" ? respondTo(match.message) : replyTo(match.message)),
          ...markup,
          caption,
          parseMode: "HTML",
          photo: new File([new Uint8Array(cover.data)], "cover.jpg", {
            type: cover.contentType ?? "image/jpeg",
          }),
        }));
        if (sent._tag === "Success") return sent.success;
      }
      return yield* answer(match.message, {
        ...markup,
        linkPreviewOptions: { isDisabled: true },
        parseMode: "HTML",
        text: caption,
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
