import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";

import type { Fetch } from "../src/app/http.ts";
import {
  commandUpdate,
  fixture,
  richContent,
  testConfig,
} from "./harness.ts";

const presence = () => [FakeBotApiReply.ok(true), FakeBotApiReply.ok(true)] as const;

function translationResponse(...sentences: ReadonlyArray<string>): Response {
  const result = [
    null,
    [[[null, null, null, null, null, sentences.map((text) => [text])]], "fr", null, "en"],
    "en",
  ];
  const payload = JSON.stringify([["wrb.fr", "MkEWBc", JSON.stringify(result), null, null, "0"]]);
  return new Response(`)]}'\n\n${payload}\n`);
}

test("define command renders the first dictionary meaning", async () => {
  const send: Fetch = async () => new Response(JSON.stringify([{
    meanings: [{
      definitions: [{ definition: "Existing after death.", synonyms: ["late", "postmortem"] }],
      partOfSpeech: "adjective",
    }],
    phonetics: [{ text: "/ˈpɒstjʊməs/" }],
    word: "posthumous",
  }]));
  const { app, bot, database, fake } = await fixture(send, presence());

  try {
    await app.run(bot.handler(commandUpdate("/define posthumous", 201)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("Existing after death.");
  expect(content.text).toContain("late");
  expect(content.types).toContain("details");
});

test("Urban Dictionary command selects the highest-voted definition", async () => {
  const send: Fetch = async () => new Response(JSON.stringify({
    list: [
      {
        definition: "weak definition",
        example: "first",
        permalink: "https://urban.example/first",
        thumbs_up: 2,
        word: "based",
      },
      {
        definition: "strong definition",
        example: "second",
        permalink: "https://urban.example/second",
        thumbs_up: 91,
        word: "based",
      },
    ],
  }));
  const { app, bot, database, fake } = await fixture(send, presence());

  try {
    await app.run(bot.handler(commandUpdate("/ud based", 202)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(content.text).toContain("strong definition");
  expect(content.text).not.toContain("weak definition");
  expect(content.types).toContain("blockquote");
});

test("calculation command explains an unrecognized query", async () => {
  const send: Fetch = async () => new Response("Wolfram did not understand", { status: 501 });
  const { app, bot, database, fake } = await fixture(
    send,
    presence(),
    testConfig({ wolframAppId: "wolfram-test" }),
  );

  try {
    await app.run(bot.handler(commandUpdate("/calc ambiguous thing", 203)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: "❌ I couldn't understand that query." });
});

test("translate command sends the complete translated text", async () => {
  let requestUrl = "";
  let requestMethod = "";
  const send: Fetch = async (input, options) => {
    requestUrl = String(input);
    requestMethod = options?.method ?? "GET";
    return translationResponse("Bonjour.", "Bonne matinée.");
  };
  const { app, bot, database, fake } = await fixture(send, presence());

  try {
    await app.run(bot.handler(commandUpdate("/tl fr - Good morning", 204)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: "Bonjour. Bonne matinée." });
  expect(new URL(requestUrl).pathname).toBe("/_/TranslateWebserverUi/data/batchexecute");
  expect(requestMethod).toBe("POST");
});

test("translate command rejects an unknown language before requesting a translation", async () => {
  let requests = 0;
  const { app, bot, database, fake } = await fixture(async () => {
    requests += 1;
    return translationResponse("Hello");
  }, presence());

  try {
    await app.run(bot.handler(commandUpdate("/tl klingon - Hello", 206)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: "Invalid target language: klingon" });
  expect(requests).toBe(0);
});

test.each([
  { status: 429, body: "<html>Automated queries blocked</html>", message: "Translation is temporarily rate-limited. Please try again later." },
  { status: 503, body: "Service unavailable", message: "Translation service is unavailable. Please try again later." },
  { status: 200, body: "<html>Unexpected response</html>", message: "Translation service is unavailable. Please try again later." },
])("translate command reports provider failure for $status", async ({ status, body, message }) => {
  let requests = 0;
  const { app, bot, database, fake } = await fixture(async () => {
    requests += 1;
    return new Response(body, { status });
  }, presence());

  try {
    await app.run(bot.handler(commandUpdate("/tl Bonjour", 207)));
  } finally {
    await app.close();
    database.close();
  }

  const reply = fake.requests.find((request) => request.method === "sendMessage");
  expect(reply?.params).toMatchObject({ text: message });
  expect(requests).toBe(1);
});

test("weather command stores the resolved location and renders air quality", async () => {
  const send: Fetch = async (input) => {
    const url = String(input);
    if (url.startsWith("https://api.weatherapi.com")) {
      return new Response(JSON.stringify({
        current: {
          air_quality: { pm10: 21.25, pm2_5: 8.75 },
          condition: { text: "Clear" },
          feelslike_c: 17.75,
          humidity: 61,
          temp_c: 18.25,
          wind_dir: "NW",
          wind_kph: 12.5,
        },
        location: {
          country: "Germany",
          lat: 52.52,
          localtime: "2026-09-01 14:00",
          lon: 13.405,
          name: "Berlin",
          region: "Berlin",
        },
      }));
    }
    return new Response(JSON.stringify({ data: { aqi: 42 }, status: "ok" }));
  };
  const { app, bot, database, fake } = await fixture(
    send,
    presence(),
    testConfig({ waqiApiKey: "waqi-test", weatherApiKey: "weather-test" }),
  );

  try {
    await app.run(bot.handler(commandUpdate("/weather Berlin", 205)));
  } finally {
    await app.close();
  }
  const cached = await Effect.runPromise(database.one(
    "SELECT latitude, longitude, address FROM weather_cache WHERE user_id = ?",
    [1],
  ));
  database.close();

  const reply = fake.requests.find((request) => request.method === "sendRichMessage");
  const content = richContent(reply?.params);
  expect(cached?.["address"]).toBe("Berlin, Berlin, Germany");
  expect(cached?.["latitude"]).toBe(52.52);
  expect(content.text).toContain("AQI\n42");
  expect(content.types).toContain("table");
});
