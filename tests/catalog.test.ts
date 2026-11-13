import { expect, test } from "bun:test";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import { bookGenres } from "../src/features/catalog.ts";
import { commandUpdate, fixture, sentMessage, testConfig } from "./harness.ts";

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

const multiAuthorBook = `<GoodreadsResponse><book>
  <title><![CDATA[Good Omens (Omens, #1)]]></title>
  <image_url><![CDATA[https://images.test/books/1l/12070._SX98_.jpg]]></image_url>
  <publication_year>2007</publication_year>
  <work><ratings_count type="integer">851234</ratings_count><original_publication_year type="integer">1990</original_publication_year></work>
  <average_rating>4.25</average_rating><num_pages><![CDATA[384]]></num_pages>
  <description><![CDATA[The world will end on Saturday.]]></description>
  <authors>
    <author><name>Neil Gaiman</name><role></role></author>
    <author><name>Terry Pratchett</name><role></role></author>
    <author><name>Somebody Else</name><role>Illustrator</role></author>
  </authors>
  <url><![CDATA[https://www.goodreads.com/book/show/12070]]></url>
  <popular_shelves><shelf name="to-read" count="9"/><shelf name="fantasy" count="8"/><shelf name="favorites" count="7"/><shelf name="humor" count="6"/></popular_shelves>
</book></GoodreadsResponse>`;

function goodreads(cover: () => Response): Fetch {
  return async (input) => {
    const url = String(input);
    if (url.startsWith("https://www.goodreads.com/search.xml")) {
      return new Response(`<GoodreadsResponse><search><results><work><best_book><id>12070</id></best_book></work></results></search></GoodreadsResponse>`);
    }
    if (url.startsWith("https://www.goodreads.com/book/show.xml")) return new Response(multiAuthorBook);
    expect(url).toBe("https://images.test/books/1l/12070.jpg");
    return cover();
  };
}

test("book command sends a multi-author book as a cover photo with a rich caption", async () => {
  const { app, bot, database, fake } = await fixture(
    goodreads(() => new Response("cover-bytes", { headers: { "content-type": "image/jpeg" } })),
    [...presence(), sentMessage(1_102)],
    testConfig({ goodreadsApiKey: "goodreads-test" }),
  );

  try {
    await app.run(bot.handler(commandUpdate("/book good omens", 1_102)));
  } finally {
    await app.close();
    database.close();
  }

  const photo = fake.requests.find((request) => request.method === "sendPhoto");
  const caption = String(Reflect.get(Object(photo?.params), "caption"));
  expect(caption).toContain("<b>Good Omens</b>\n<i>Omens #1</i>\nNeil Gaiman, Terry Pratchett · 1990");
  expect(caption).toContain("⭐ 4.25 (851.2K ratings) · 384 pages");
  expect(caption).toContain("🏷 Fantasy · Humor");
  expect(caption).toContain("<blockquote expandable>The world will end on Saturday.</blockquote>");
  expect(caption).not.toContain("Somebody Else");
  expect(JSON.stringify(photo?.params)).toContain("https://www.goodreads.com/book/show/12070");
  expect(fake.requests.some((request) => request.method === "sendMessage")).toBe(false);
});

test("book command falls back to text when the cover cannot be fetched", async () => {
  const { app, bot, database, fake } = await fixture(
    goodreads(() => new Response("missing", { status: 404 })),
    [...presence(), sentMessage(1_103)],
    testConfig({ goodreadsApiKey: "goodreads-test" }),
  );

  try {
    await app.run(bot.handler(commandUpdate("/book good omens", 1_103)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(String(Reflect.get(Object(reply?.params), "text"))).toContain("<b>Good Omens</b>");
  expect(fake.requests.some((request) => request.method === "sendPhoto")).toBe(false);
});

test("book genres skip reading-status shelves and merge aliases", () => {
  const xml = ["to-read", "currently-reading", "sci-fi", "science-fiction", "owned", "did-not-finish", "fiction", "2024-reads", "classics"]
    .map((name) => `<shelf name="${name}" count="1"/>`).join("");
  expect(bookGenres(xml)).toEqual(["Science Fiction", "Fiction", "Classics"]);
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
