import * as Semaphore from "effect/Semaphore";
import {
  answerCallback,
  callbackData,
  Effect,
  html,
  Schema,
  sendMessage,
} from "telly";

import { callbackRoute } from "../app/callback.ts";
import { answer, type CommandDefinition } from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const competitions = [
  { name: "Premier League", slug: "eng.1" },
  { name: "Champions League", slug: "uefa.champions" },
  { name: "FA Cup", slug: "eng.fa" },
] as const;
const trackedTeams = new Set([
  "Arsenal",
  "Chelsea",
  "Liverpool",
  "Manchester City",
  "Manchester United",
  "Tottenham Hotspur",
]);
const scheduled = "STATUS_SCHEDULED";
const footballLock = Semaphore.makeUnsafe(1);
const FootballCallback = callbackData("football", Schema.Struct({
  action: Schema.Literals(["join", "leave"]),
}));

const Competition = Schema.Struct({
  competitors: Schema.Array(Schema.Struct({
    homeAway: Schema.String,
    team: Schema.Struct({ displayName: Schema.String }),
  })),
  date: Schema.String,
  status: Schema.Struct({ type: Schema.Struct({ name: Schema.String }) }),
});
const Scoreboard = Schema.Struct({
  events: Schema.Array(Schema.Struct({
    competitions: Schema.Array(Competition),
    id: Schema.String,
  })),
});
const Summary = Schema.Struct({
  header: Schema.Struct({
    competitions: Schema.Array(Competition),
    id: Schema.String,
  }),
});
const Market = Schema.Struct({
  active: Schema.Boolean,
  closed: Schema.Boolean,
  outcomePrices: Schema.String,
  outcomes: Schema.String,
  question: Schema.String,
  sportsMarketType: Schema.String,
});
const Polymarket = Schema.Struct({
  events: Schema.Array(Schema.Struct({
    active: Schema.Boolean,
    closed: Schema.Boolean,
    endDate: Schema.String,
    eventDate: Schema.String,
    id: Schema.Union([Schema.String, Schema.Number]),
    markets: Schema.Array(Market),
    slug: Schema.String,
    title: Schema.String,
  })),
});

interface Fixture {
  readonly awayTeam: string;
  readonly competition: string;
  readonly competitionName: string;
  readonly homeTeam: string;
  readonly kickoffTime: number;
  readonly providerId: string;
  readonly status: string;
}

interface Odds {
  readonly away: number;
  readonly draw: number;
  readonly home: number;
  readonly slug: string;
}

function keyboard() {
  return {
    inlineKeyboard: [[
      { ...FootballCallback.button("✅ Join", { action: "join" }), style: "success" as const },
      { ...FootballCallback.button("❌ Leave", { action: "leave" }), style: "danger" as const },
    ]],
  };
}

function fixtureFrom(providerId: string, slug: string, name: string, data: typeof Competition.Type): Fixture {
  const home = data.competitors.find((team) => team.homeAway === "home")?.team.displayName;
  const away = data.competitors.find((team) => team.homeAway === "away")?.team.displayName;
  if (home === undefined || away === undefined) throw new Error("ESPN fixture has no teams");
  return {
    awayTeam: away,
    competition: slug,
    competitionName: name,
    homeTeam: home,
    kickoffTime: Math.floor(new Date(data.date).getTime() / 1_000),
    providerId,
    status: data.status.type.name,
  };
}

function tracked(fixture: Fixture): boolean {
  return competitions.some((competition) => competition.slug === fixture.competition) &&
    (trackedTeams.has(fixture.homeTeam) || trackedTeams.has(fixture.awayTeam));
}

function rowFixture(row: import("@libsql/client").Row): Fixture {
  return {
    awayTeam: rowString(row, "away_team"),
    competition: rowString(row, "competition"),
    competitionName: rowString(row, "competition_name"),
    homeTeam: rowString(row, "home_team"),
    kickoffTime: rowNumber(row, "kickoff_time"),
    providerId: rowString(row, "provider_id"),
    status: rowString(row, "status"),
  };
}

function seasonRanges(now: Date): ReadonlyArray<readonly [string, string]> {
  const year = now.getUTCMonth() >= 6 ? now.getUTCFullYear() : now.getUTCFullYear() - 1;
  const date = (value: Date) => value.toISOString().slice(0, 10).replaceAll("-", "");
  return [
    [date(new Date(Date.UTC(year, 6, 1))), date(new Date(Date.UTC(year + 1, 5, 30)))],
    [date(new Date(Date.UTC(year + 1, 6, 1))), date(new Date(Date.UTC(year + 2, 5, 30)))],
  ];
}

function storeFixtures(dependencies: AppDependencies, fixtures: ReadonlyArray<Fixture>) {
  return Effect.forEach(fixtures, (fixture) => dependencies.database.execute(
    `INSERT INTO football_fixtures (
      provider_id, competition, competition_name, home_team, away_team, kickoff_time, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(provider_id) DO UPDATE SET
      competition = excluded.competition,
      competition_name = excluded.competition_name,
      home_team = excluded.home_team,
      away_team = excluded.away_team,
      kickoff_time = excluded.kickoff_time,
      status = excluded.status,
      alert_time = CASE WHEN football_fixtures.kickoff_time != excluded.kickoff_time
        THEN NULL ELSE football_fixtures.alert_time END,
      update_time = CURRENT_TIMESTAMP`,
    [
      fixture.providerId,
      fixture.competition,
      fixture.competitionName,
      fixture.homeTeam,
      fixture.awayTeam,
      fixture.kickoffTime,
      fixture.status,
    ],
  ), { concurrency: 1, discard: true });
}

function syncFixtures(dependencies: AppDependencies) {
  const program = Effect.gen(function* () {
    for (const competition of competitions) {
      yield* Effect.gen(function* () {
        const fixtures: Array<Fixture> = [];
        for (const [start, end] of seasonRanges(dependencies.now())) {
          const url = new URL(`https://site.api.espn.com/apis/site/v2/sports/soccer/${competition.slug}/scoreboard`);
          url.search = new URLSearchParams({ dates: `${start}-${end}`, limit: "1000" }).toString();
          const response = yield* dependencies.http.json("espn", url, Scoreboard);
          fixtures.push(...response.data.events.flatMap((event) => {
            const data = event.competitions[0];
            return data === undefined ? [] : [fixtureFrom(event.id, competition.slug, competition.name, data)];
          }).filter(tracked));
        }
        yield* storeFixtures(dependencies, fixtures);
        if (fixtures.length === 0) {
          yield* dependencies.database.execute(
            "DELETE FROM football_fixtures WHERE competition = ?",
            [competition.slug],
          );
        } else {
          yield* dependencies.database.execute(
            `DELETE FROM football_fixtures WHERE competition = ?
             AND provider_id NOT IN (${fixtures.map(() => "?").join(", ")})`,
            [competition.slug, ...fixtures.map((fixture) => fixture.providerId)],
          );
        }
      }).pipe(Effect.catch((error) => Effect.logError(
        `Football fixture sync failed for ${competition.name}: ${String(error)}`,
      )));
    }
  });
  return footballLock.withPermits(1)(program);
}

function nextFixtures(dependencies: AppDependencies, now: number) {
  return dependencies.database.all(
    `SELECT provider_id, competition, competition_name, home_team, away_team, kickoff_time, status
     FROM football_fixtures WHERE status = ? AND kickoff_time > ?
     ORDER BY kickoff_time, competition_name, home_team`,
    [scheduled, now],
  ).pipe(Effect.map((rows) => {
    const values = rows.map(rowFixture).filter(tracked);
    const kickoff = values[0]?.kickoffTime;
    return kickoff === undefined ? [] : values.filter((fixture) => fixture.kickoffTime === kickoff);
  }));
}

function verifyFixture(dependencies: AppDependencies, fixture: Fixture) {
  const competition = competitions.find((item) => item.slug === fixture.competition);
  if (competition === undefined) return Effect.succeed(undefined);
  const url = new URL(`https://site.api.espn.com/apis/site/v2/sports/soccer/${fixture.competition}/summary`);
  url.searchParams.set("event", fixture.providerId);
  return dependencies.http.json("espn", url, Summary).pipe(
    Effect.flatMap((response) => {
      const data = response.data.header.competitions[0];
      if (data === undefined) return Effect.succeed(undefined);
      const current = fixtureFrom(
        response.data.header.id,
        competition.slug,
        competition.name,
        data,
      );
      return storeFixtures(dependencies, [current]).pipe(Effect.as(current));
    }),
    Effect.catch(() => Effect.succeed(undefined)),
  );
}

function words(value: string): ReadonlyArray<string> {
  return value.toLowerCase().match(/[a-z0-9]+/gu) ?? [];
}

function hasTeam(text: string, team: string): boolean {
  const source = words(text);
  const target = words(team).filter((word) => !["afc", "cf", "fc"].includes(word));
  return source.some((_, index) => target.every((word, offset) => source[index + offset] === word));
}

function yesPrice(market: typeof Market.Type): number | undefined {
  const outcomes = Schema.decodeUnknownSync(Schema.Array(Schema.String))(JSON.parse(market.outcomes));
  const prices = Schema.decodeUnknownSync(Schema.Array(Schema.String))(JSON.parse(market.outcomePrices));
  const index = outcomes.indexOf("Yes");
  const price = Number(prices[index]);
  return outcomes.length !== prices.length || index === -1 || !Number.isFinite(price) ||
      price < 0 || price > 1
    ? undefined
    : price;
}

function oddsFor(dependencies: AppDependencies, fixture: Fixture) {
  const queries = new Set([
    `${fixture.homeTeam} ${fixture.awayTeam}`,
    [fixture.homeTeam, fixture.awayTeam].filter((team) => trackedTeams.has(team)).join(" "),
  ]);
  return Effect.forEach(queries, (query) => {
    const url = new URL("https://gamma-api.polymarket.com/public-search");
    url.search = new URLSearchParams({
      events_status: "active",
      limit_per_type: "50",
      q: query,
      search_profiles: "false",
    }).toString();
    return dependencies.http.json("polymarket", url, Polymarket).pipe(
      Effect.map((response) => response.data.events),
    );
  }, { concurrency: "unbounded" }).pipe(
    Effect.map((groups) => [...new Map(groups.flat().map((event) => [String(event.id), event])).values()]),
    Effect.map((events) => events.find((event) =>
      event.slug.startsWith(`${fixture.competition === "eng.1" ? "epl" : fixture.competition === "uefa.champions" ? "ucl" : "efa"}-`) &&
      event.active && !event.closed &&
      event.eventDate === new Date(fixture.kickoffTime * 1_000).toISOString().slice(0, 10) &&
      (hasTeam(event.title, fixture.homeTeam) || hasTeam(event.title, fixture.awayTeam)))),
    Effect.map((event): Odds | undefined => {
      if (event === undefined) return undefined;
      const markets = event.markets.filter((item) =>
        item.sportsMarketType === "moneyline" && item.active && !item.closed);
      if (markets.length !== 3) return undefined;
      const values: Record<"away" | "draw" | "home", Array<number>> = {
        away: [],
        draw: [],
        home: [],
      };
      const unmatched: Array<number> = [];
      for (const market of markets) {
        const price = yesPrice(market);
        if (price === undefined) return undefined;
        if (words(market.question).includes("draw")) values.draw.push(price);
        else if (hasTeam(market.question, fixture.homeTeam)) values.home.push(price);
        else if (hasTeam(market.question, fixture.awayTeam)) values.away.push(price);
        else unmatched.push(price);
      }
      if (Object.values(values).some((prices) => prices.length > 1)) return undefined;
      const missing = (["home", "away"] as const).filter((side) => values[side].length === 0);
      if (missing.length === 1 && unmatched.length === 1) values[missing[0]!] = unmatched;
      const home = values.home[0];
      const draw = values.draw[0];
      const away = values.away[0];
      return home === undefined || draw === undefined || away === undefined
        ? undefined
        : { away, draw, home, slug: event.slug };
    }),
    Effect.catch(() => Effect.succeed(undefined)),
  );
}

function streamLinks(dependencies: AppDependencies) {
  return dependencies.http.text("streameast", "https://thestreameast.one/", {
    headers: { "user-agent": "Mozilla/5.0 SuperSeriousBot" },
  }).pipe(
    Effect.map((response) => [...response.data.matchAll(/<a href="(https:\/\/thestreameast\.one\/watch\/[^"]+)".*?<span\s+class="d-md-inline[^"]*">\s*(.*?)\s*<\/span>/gisu)].flatMap((match) => {
      const title = match[2]?.replace(/<[^>]+>/gu, "").trim();
      const parts = title?.split(" vs ");
      return match[1] === undefined || parts?.length !== 2
        ? []
        : [{ away: parts[1] ?? "", home: parts[0] ?? "", url: match[1] }];
    })),
    Effect.catch(() => Effect.succeed([])),
  );
}

function renderFixtures(fixtures: ReadonlyArray<Fixture>, odds: ReadonlyMap<string, Odds>, streams: ReadonlyArray<{ readonly away: string; readonly home: string; readonly url: string }>, heading: string) {
  const lines = [heading];
  let competition = "";
  for (const fixture of fixtures) {
    if (fixture.competitionName !== competition) {
      competition = fixture.competitionName;
      lines.push("", `<b>${html.escape(competition)}</b>`);
    }
    const stream = streams.find((item) =>
      hasTeam(item.home, fixture.homeTeam) && hasTeam(item.away, fixture.awayTeam) ||
      hasTeam(item.home, fixture.awayTeam) && hasTeam(item.away, fixture.homeTeam));
    lines.push(`• ${html.escape(fixture.homeTeam)} vs ${html.escape(fixture.awayTeam)}${stream === undefined ? "" : ` · <a href="${stream.url}">📺 watch</a>`}`);
  }
  lines.push("", `<tg-time unix="${fixtures[0]?.kickoffTime ?? 0}" format="r">Kickoff</tg-time>`, "", "📊 <b>Polymarket odds</b>");
  for (const fixture of fixtures) {
    const value = odds.get(fixture.providerId);
    lines.push(value === undefined
      ? `• ${html.escape(fixture.homeTeam)} vs ${html.escape(fixture.awayTeam)}: not available yet`
      : `• ${html.escape(fixture.homeTeam)} <b>${(value.home * 100).toFixed(0)}%</b> · Draw <b>${(value.draw * 100).toFixed(0)}%</b> · ${html.escape(fixture.awayTeam)} <b>${(value.away * 100).toFixed(0)}%</b> · <a href="https://polymarket.com/event/${value.slug}">market</a>`);
  }
  return lines.join("\n");
}

export function footballFeature(dependencies: AppDependencies) {
  const next: CommandDefinition = {
    description: "Show the countdown to the next Big Six match.",
    example: "/next",
    names: ["next"],
    run: Effect.fn("nextMatch")(function* (match) {
      const fixtures = yield* nextFixtures(
        dependencies,
        Math.floor(dependencies.now().getTime() / 1_000),
      );
      if (fixtures.length === 0) return yield* answer(
        match.message,
        "No upcoming Big Six matches found.",
      );
      const [oddsValues, streams] = yield* Effect.all([
        Effect.forEach(fixtures, (fixture) => oddsFor(dependencies, fixture).pipe(
          Effect.map((odds) => [fixture.providerId, odds] as const),
        ), { concurrency: "unbounded" }),
        streamLinks(dependencies),
      ], { concurrency: "unbounded" });
      const odds = new Map(oddsValues.filter((entry): entry is readonly [string, Odds] => entry[1] !== undefined));
      yield* answer(match.message, {
        linkPreviewOptions: { isDisabled: true },
        parseMode: "HTML",
        text: renderFixtures(fixtures, odds, streams, "⚽ <b>Next Big Six match</b>"),
      });
    }),
    usage: "/next",
  };
  const alerts: CommandDefinition = {
    description: "Join five-minute Big Six football alerts for this group.",
    example: "/football",
    names: ["football"],
    run: Effect.fn("footballAlerts")(function* (match) {
      const user = match.message.from;
      if (match.message.chat.type === "private") return yield* answer(
        match.message,
        "Football alerts can only be used in group chats.",
      );
      if (user === undefined) return;
      yield* dependencies.database.execute(
        `INSERT INTO football_alert_members (chat_id, user_id, display_name)
         VALUES (?, ?, ?)
         ON CONFLICT(chat_id, user_id) DO UPDATE SET display_name = excluded.display_name`,
        [match.message.chat.id, user.id, `${user.firstName}${user.lastName === undefined ? "" : ` ${user.lastName}`}`],
      );
      yield* answer(match.message, {
        parseMode: "HTML",
        replyMarkup: keyboard(),
        text: "⚽ <b>Football alerts enabled</b>\n\nYou'll be tagged five minutes before Big Six matches in the Premier League, Champions League and FA Cup.",
      });
    }),
    usage: "/football",
  };
  const callback = callbackRoute("football", FootballCallback, Effect.fn("footballCallback")(function* ({ callbackQuery, data }) {
    const message = callbackQuery.message;
    if (message === undefined) return;
    if (data.action === "join") {
      yield* dependencies.database.execute(
        `INSERT INTO football_alert_members (chat_id, user_id, display_name)
         VALUES (?, ?, ?)
         ON CONFLICT(chat_id, user_id) DO UPDATE SET display_name = excluded.display_name`,
        [message.chat.id, callbackQuery.from.id, callbackQuery.from.firstName],
      );
      yield* answerCallback(callbackQuery, { text: "Joined football alerts." });
      return;
    }
    yield* dependencies.database.execute(
      "DELETE FROM football_alert_members WHERE chat_id = ? AND user_id = ?",
      [message.chat.id, callbackQuery.from.id],
    );
    yield* answerCallback(callbackQuery, { text: "Left football alerts." });
  }));
  const sync = Effect.fn("syncFootballFixtures")(function* () {
    yield* syncFixtures(dependencies);
  }, Effect.catch(() => Effect.logError("Football fixture sync failed")));
  const notify = Effect.fn("footballAlertsWorker")(function* () {
    const now = Math.floor(dependencies.now().getTime() / 1_000);
    const dueRows = yield* dependencies.database.all(
      `SELECT provider_id, competition, competition_name, home_team, away_team, kickoff_time, status
       FROM football_fixtures
       WHERE status = ? AND alert_time IS NULL AND kickoff_time > ? AND kickoff_time <= ?
       ORDER BY kickoff_time, competition_name, home_team`,
      [scheduled, now, now + 360],
    );
    const due = dueRows.map(rowFixture).filter(tracked);
    const verified = yield* Effect.forEach(due, (fixture) => verifyFixture(
      dependencies,
      fixture,
    ), { concurrency: 4 });
    const fixtures = verified.filter((fixture): fixture is Fixture =>
      fixture !== undefined && fixture.status === scheduled &&
      fixture.kickoffTime > now && fixture.kickoffTime <= now + 360);
    if (fixtures.length === 0) return;
    const [oddsValues, streams] = yield* Effect.all([
      Effect.forEach(fixtures, (fixture) => oddsFor(dependencies, fixture).pipe(
        Effect.map((odds) => [fixture.providerId, odds] as const),
      ), { concurrency: "unbounded" }),
      streamLinks(dependencies),
    ], { concurrency: "unbounded" });
    const odds = new Map(oddsValues.filter(
      (entry): entry is readonly [string, Odds] => entry[1] !== undefined,
    ));
    const chats = yield* dependencies.database.all(
      "SELECT DISTINCT chat_id FROM football_alert_members ORDER BY chat_id",
    );
    for (const chat of chats) {
      const chatId = rowNumber(chat, "chat_id");
      const memberRows = yield* dependencies.database.all(
        "SELECT user_id, display_name FROM football_alert_members WHERE chat_id = ? ORDER BY create_time, user_id",
        [chatId],
      );
      const deliveredRows = yield* dependencies.database.all(
        `SELECT provider_id, user_id FROM football_alert_deliveries
         WHERE chat_id = ? AND kickoff_time = ?`,
        [chatId, fixtures[0]!.kickoffTime],
      );
      const delivered = new Set(deliveredRows.map((row) =>
        `${rowString(row, "provider_id")}:${rowNumber(row, "user_id")}`));
      const members = memberRows.filter((member) => fixtures.some((fixture) =>
        !delivered.has(`${fixture.providerId}:${rowNumber(member, "user_id")}`)));
      for (let index = 0; index < members.length; index += 5) {
        const chunk = members.slice(index, index + 5);
        const mentions = chunk.map((member) => `<a href="tg://user?id=${rowNumber(member, "user_id")}">${html.escape(rowString(member, "display_name"))}</a>`).join(" ");
        const result = yield* Effect.result(sendMessage({
          chatId,
          linkPreviewOptions: { isDisabled: true },
          parseMode: "HTML",
          replyMarkup: keyboard(),
          text: `${renderFixtures(fixtures, odds, streams, "⚽ <b>Kickoff in five minutes</b>")}\n\n${mentions}`,
        }));
        if (result._tag === "Failure") continue;
        yield* Effect.forEach(chunk, (member) => Effect.forEach(fixtures, (fixture) =>
          dependencies.database.execute(
            `INSERT OR IGNORE INTO football_alert_deliveries (
              provider_id, kickoff_time, chat_id, user_id, delivery_time
            ) VALUES (?, ?, ?, ?, ?)`,
            [fixture.providerId, fixture.kickoffTime, chatId, rowNumber(member, "user_id"), now],
          ), { concurrency: 1, discard: true }), { concurrency: 1, discard: true });
      }
    }
    yield* Effect.forEach(fixtures, (fixture) => dependencies.database.execute(
      `UPDATE football_fixtures SET alert_time = ?, update_time = CURRENT_TIMESTAMP
       WHERE provider_id = ? AND kickoff_time = ? AND alert_time IS NULL
         AND NOT EXISTS (
           SELECT 1 FROM football_alert_members members
           WHERE NOT EXISTS (
             SELECT 1 FROM football_alert_deliveries deliveries
             WHERE deliveries.provider_id = football_fixtures.provider_id
               AND deliveries.kickoff_time = football_fixtures.kickoff_time
               AND deliveries.chat_id = members.chat_id
               AND deliveries.user_id = members.user_id
           )
         )`,
      [now, fixture.providerId, fixture.kickoffTime],
    ), { concurrency: 1, discard: true });
  });
  return { callback, commands: [next, alerts] as const, workers: { notify, sync } };
}
