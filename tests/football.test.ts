import { expect, test } from "bun:test";
import { Effect, type Update } from "telly";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture } from "./harness.ts";

const kickoff = Math.floor(new Date("2026-09-01T12:05:00Z").getTime() / 1_000);

function competition(
  home = "Arsenal",
  away = "Coventry City",
  date = "2026-09-01T12:05:00Z",
) {
  return {
    competitors: [
      { homeAway: "home", team: { displayName: home } },
      { homeAway: "away", team: { displayName: away } },
    ],
    date,
    status: { type: { name: "STATUS_SCHEDULED" } },
  };
}

function polymarket() {
  const market = (question: string, price: string) => ({
    active: true,
    closed: false,
    outcomePrices: JSON.stringify([price, "0.50"]),
    outcomes: JSON.stringify(["Yes", "No"]),
    question,
    sportsMarketType: "moneyline",
  });
  return {
    events: [{
      active: true,
      closed: false,
      endDate: "2026-09-01T14:00:00Z",
      eventDate: "2026-09-01",
      id: "market-1",
      markets: [
        market("Will Arsenal win?", "0.62"),
        market("Will the match end in a draw?", "0.23"),
        market("Will the Sky Blues win?", "0.15"),
      ],
      slug: "epl-ars-cov-2026-09-01",
      title: "Arsenal FC vs Coventry City",
    }],
  };
}

function streamPage() {
  return `<a href="https://thestreameast.one/watch/premier-league/arsenal-coventry/1">
    <span class="d-md-inline ">Arsenal vs Coventry City</span>
  </a>`;
}

function requestText(params: unknown): string {
  if (typeof params !== "object" || params === null) throw new Error("Telegram request missing");
  const text = Reflect.get(params, "text");
  if (typeof text !== "string") throw new Error("Telegram request has no text");
  return text;
}

async function storeFixture(
  database: Awaited<ReturnType<typeof fixture>>["database"],
) {
  await Effect.runPromise(database.execute(
    `INSERT INTO football_fixtures (
      provider_id, competition, competition_name, home_team, away_team,
      kickoff_time, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [
      "match-1",
      "eng.1",
      "Premier League",
      "Arsenal",
      "Coventry City",
      kickoff,
      "STATUS_SCHEDULED",
    ],
  ));
}

test("football sync keeps syncing after one competition fails", async () => {
  const send: Fetch = async (input) => {
    const url = String(input);
    if (url.includes("/eng.1/")) throw new Error("Premier League is unavailable");
    if (url.includes("/uefa.champions/")) return new Response(JSON.stringify({
      events: [{ competitions: [competition("Liverpool", "Real Madrid")], id: "ucl-7" }],
    }));
    return new Response(JSON.stringify({ events: [] }));
  };
  const { app, bot, database } = await fixture(send);

  try {
    await app.run(bot.workers.football.sync());
  } finally {
    await app.close();
  }
  const rows = await Effect.runPromise(database.all(
    "SELECT provider_id, competition, home_team FROM football_fixtures",
  ));
  database.close();

  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({
    competition: "uefa.champions",
    home_team: "Liverpool",
    provider_id: "ucl-7",
  });
});

test("next command renders odds and a matching watch link", async () => {
  const send: Fetch = async (input) => String(input).includes("polymarket")
    ? new Response(JSON.stringify(polymarket()))
    : new Response(streamPage(), { headers: { "content-type": "text/html" } });
  const { app, bot, database, fake } = await fixture(send);
  await storeFixture(database);

  try {
    await app.run(bot.handler(commandUpdate("/next", 4_001)));
  } finally {
    await app.close();
    database.close();
  }

  const message = fake.requests.find((request) => request.method === "sendMessage");
  const text = requestText(message?.params);
  expect(message?.params).toMatchObject({
    link_preview_options: { is_disabled: true },
    parse_mode: "HTML",
  });
  expect(text).toContain("Arsenal <b>62%</b> · Draw <b>23%</b> · Coventry City <b>15%</b>");
  expect(text).toContain("📺 watch</a>");
});

test("football buttons join and leave the current group", async () => {
  const offline: Fetch = async () => new Response("{}");
  const { app, bot, database, fake } = await fixture(offline);

  try {
    await app.run(bot.handler(commandUpdate("/football", 4_002)));
    const request = fake.requests.find((item) => item.method === "sendMessage");
    const markup = Reflect.get(request?.params ?? {}, "reply_markup");
    const rows = Reflect.get(markup, "inline_keyboard") as ReadonlyArray<ReadonlyArray<Record<string, string>>>;
    const join = rows[0]?.find((button) => button["text"] === "✅ Join")?.["callback_data"];
    const leave = rows[0]?.find((button) => button["text"] === "❌ Leave")?.["callback_data"];
    if (join === undefined || leave === undefined) throw new Error("Football buttons missing");
    const callback = (updateId: number, data: string): Update => ({
      callbackQuery: {
        chatInstance: "football-chat",
        data,
        from: { firstName: "Alice", id: 2, isBot: false, username: "alice" },
        id: `football-${updateId}`,
        message: {
          chat: { id: -1007, title: "Telly Lab", type: "supergroup" },
          date: 1_700_000_001,
          messageId: 4_002,
        },
      },
      updateId,
    });
    await app.run(bot.handler(callback(4_003, join)));
    await app.run(bot.handler(callback(4_004, leave)));
  } finally {
    await app.close();
  }
  const alice = await Effect.runPromise(database.one(
    "SELECT user_id FROM football_alert_members WHERE chat_id = ? AND user_id = ?",
    [-1007, 2],
  ));
  database.close();

  expect(alice).toBeUndefined();
  const answers = fake.requests.filter((request) => request.method === "answerCallbackQuery");
  expect(answers.map((request) => Reflect.get(request.params ?? {}, "text"))).toEqual([
    "Joined football alerts.",
    "Left football alerts.",
  ]);
});

test("football worker delivers rich alerts once per member", async () => {
  const send: Fetch = async (input) => {
    const url = String(input);
    if (url.includes("/summary")) return new Response(JSON.stringify({
      header: { competitions: [competition()], id: "match-1" },
    }));
    if (url.includes("polymarket")) return new Response(JSON.stringify(polymarket()));
    return new Response(streamPage(), { headers: { "content-type": "text/html" } });
  };
  const { app, bot, database, fake } = await fixture(send);
  await storeFixture(database);
  await Effect.runPromise(database.execute(
    `INSERT INTO football_alert_members (chat_id, user_id, display_name)
     VALUES (?, ?, ?)`,
    [-1007, 7, "Ayaan & Co"],
  ));

  try {
    await app.run(bot.workers.football.notify());
    await Effect.runPromise(database.execute(
      "UPDATE football_fixtures SET alert_time = NULL WHERE provider_id = ?",
      ["match-1"],
    ));
    await app.run(bot.workers.football.notify());
  } finally {
    await app.close();
  }
  const deliveries = await Effect.runPromise(database.all(
    "SELECT provider_id, chat_id, user_id FROM football_alert_deliveries",
  ));
  const fixtureRow = await Effect.runPromise(database.one(
    "SELECT alert_time FROM football_fixtures WHERE provider_id = ?",
    ["match-1"],
  ));
  database.close();

  const alerts = fake.requests.filter((request) => request.method === "sendMessage");
  const text = requestText(alerts[0]?.params);
  expect(alerts).toHaveLength(1);
  expect(text).toContain("Arsenal <b>62%</b>");
  expect(text).toContain("Ayaan &amp; Co");
  expect(deliveries).toHaveLength(1);
  expect(fixtureRow?.["alert_time"]).toBe(Math.floor(new Date("2026-09-01T12:00:00Z").getTime() / 1_000));
});
