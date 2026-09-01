import { expect, test } from "bun:test";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, testConfig } from "./harness.ts";

const presence = () => [FakeBotApiReply.ok(true), FakeBotApiReply.ok(true)] as const;

test("book command renders Goodreads details from both XML requests", async () => {
  const send: Fetch = async (input) => {
    const url = String(input);
    if (url.startsWith("https://www.goodreads.com/search.xml")) {
      return new Response(`<GoodreadsResponse><search><results><work><best_book><id>42</id></best_book></work></results></search></GoodreadsResponse>`);
    }
    return new Response(`<GoodreadsResponse><book><title>The Test Book</title><isbn13>9781234567890</isbn13><publication_year>2026</publication_year><average_rating>4.5</average_rating><num_pages>321</num_pages><url>https://goodreads.example/book</url><description>&lt;b&gt;A useful book.&lt;/b&gt;</description><authors><author><name>Ada Author</name></author></authors></book></GoodreadsResponse>`);
  };
  const { app, bot, database, fake } = await fixture(
    send,
    presence(),
    testConfig({ goodreadsApiKey: "goodreads-test" }),
  );

  try {
    await app.run(bot.handler(commandUpdate("/book The Test Book", 1_101)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  const text = typeof reply?.params === "object" && reply.params !== null
    ? Reflect.get(reply.params, "text")
    : undefined;
  expect(text).toContain("The Test Book");
  expect(text).toContain("Ada Author");
  expect(text).toContain("321 pages");
});

test("hltb command discovers the current endpoint and selects the closest game", async () => {
  const send: Fetch = async (input, init) => {
    const url = String(input);
    if (url === "https://howlongtobeat.com/") {
      return new Response(`<script src="/_next/static/chunks/search.js"></script>`);
    }
    if (url.endsWith("search.js")) {
      return new Response(`fetch("/api/finder/v2", { method: "POST" })`);
    }
    if (url.includes("/api/finder/v2/init")) {
      return new Response(JSON.stringify({ keyName: "key-field", token: "auth", valueName: "value-field" }));
    }
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    expect(body.searchTerms).toEqual(["Horizon", "Zero", "Dawn"]);
    return new Response(JSON.stringify({
      data: [
        { comp_main: 3_600, game_name: "Horizon Chase" },
        { comp_main: 108_000, game_image: "horizon.jpg", game_name: "Horizon Zero Dawn" },
      ],
    }));
  };
  const { app, bot, database, fake } = await fixture(send, presence());

  try {
    await app.run(bot.handler(commandUpdate("/hltb Horizon Zero Dawn", 1_102)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  const text = typeof reply?.params === "object" && reply.params !== null
    ? Reflect.get(reply.params, "text")
    : undefined;
  expect(text).toContain("Horizon Zero Dawn");
  expect(text).toContain("30.00 hours");
});
