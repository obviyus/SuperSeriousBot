import { expect, test } from "bun:test";
import { Effect } from "telly";
import { FakeBotApiReply } from "telly/testing";
import sharp from "sharp";

import type { Fetch } from "../src/app/http.ts";
import { commandUpdate, fixture, openRouterText, sentMessage, testConfig } from "./harness.ts";

async function allow(
  database: Awaited<ReturnType<typeof fixture>>["database"],
  command: string,
) {
  await Effect.runPromise(database.execute(
    `INSERT INTO command_whitelist (command, whitelist_type, whitelist_id)
     VALUES (?, 'chat', ?)`,
    [command, -1007],
  ));
}

test("cron command stores the AI-planned schedule", async () => {
  const send: Fetch = async () => openRouterText(JSON.stringify({
          cronExpr: "0 9 * * *",
          task: "Check the DJI camera price and report it.",
          timezone: "Asia/Kolkata",
          title: "DJI price check",
        }));
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(201),
    FakeBotApiReply.ok(true),
  ], config);
  await allow(database, "cron");

  try {
    await app.run(bot.handler(commandUpdate("/cron daily at 9 check the DJI price", 2_001)));
  } finally {
    await app.close();
  }
  const task = await Effect.runPromise(database.one(
    `SELECT title, task, cron_expr, timezone, next_run_time
     FROM cron_tasks WHERE chat_id = ? AND user_id = ?`,
    [-1007, 1],
  ));
  database.close();

  expect(task).toMatchObject({
    cron_expr: "0 9 * * *",
    task: "Check the DJI camera price and report it.",
    timezone: "Asia/Kolkata",
    title: "DJI price check",
  });
  expect(task?.["next_run_time"]).toBe(1_788_319_800);
});

test("cron worker delivers one due task and schedules its next run", async () => {
  const send: Fetch = async () => openRouterText("The camera costs **₹42,000**.");
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database, fake } = await fixture(send, [sentMessage(202)], config);
  await Effect.runPromise(database.batch([
    {
      args: [1, "obviyus"],
      sql: "INSERT INTO user_stats (user_id, username) VALUES (?, ?)",
    },
    {
      args: [-1007, 1, "DJI price", "Find the current price", "0 9 * * *", "UTC", 1],
      sql: `INSERT INTO cron_tasks (
        chat_id, user_id, title, task, cron_expr, timezone, next_run_time
      ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
    },
  ]));

  try {
    await app.run(bot.workers.cron());
  } finally {
    await app.close();
  }
  const run = await Effect.runPromise(database.one(
    "SELECT status, result_text FROM cron_runs WHERE cron_task_id = 1",
  ));
  const task = await Effect.runPromise(database.one(
    "SELECT next_run_time, claim_time, attempt_count FROM cron_tasks WHERE id = 1",
  ));
  database.close();

  const delivered = fake.requests.find((request) => request.method === "sendMessage");
  expect(delivered?.params).toMatchObject({
    chat_id: -1007,
    text: expect.stringContaining("The camera costs *₹42,000*"),
  });
  expect(run).toMatchObject({ result_text: "The camera costs **₹42,000**.", status: "success" });
  expect(task).toMatchObject({ attempt_count: 1, claim_time: null, next_run_time: 1_788_339_600 });
});

test("song command delivers both generated tracks", async () => {
  const send: Fetch = async (input) => {
    const url = String(input);
    if (url.includes("chat/completions")) return openRouterText(JSON.stringify({
        lyricsLines: ["[Verse]", "Spreadsheets dance tonight"],
        style: "disco funk",
        title: "Cell Party",
      }));
    if (url.endsWith("/generate")) return new Response(JSON.stringify({
      code: 200,
      data: { taskId: "song-job-7" },
    }), { status: 200 });
    return new Response(JSON.stringify({
      code: 200,
      data: {
        response: { sunoData: [
          { audioUrl: "https://media.test/first.mp3", title: "Cell Party A" },
          { audioUrl: "https://media.test/second.mp3", title: "Cell Party B" },
        ] },
        status: "SUCCESS",
      },
    }));
  };
  const config = {
    ...testConfig({ kieApiKey: "kie-test", openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const generatedMessage = {
    chat: { id: -1007, type: "supergroup" },
    date: 1_700_000_001,
    message_id: 205,
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(203),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok([generatedMessage, { ...generatedMessage, message_id: 206 }]),
  ], config);
  await allow(database, "song");

  try {
    await app.run(bot.handler(commandUpdate("/song disco spreadsheet party", 2_003)));
  } finally {
    await app.close();
    database.close();
  }

  const mediaGroup = fake.requests.find((request) => request.method === "sendMediaGroup");
  expect(mediaGroup?.params).toMatchObject({
    chat_id: -1007,
    media: [
      { media: "https://media.test/first.mp3", title: "Cell Party A", type: "audio" },
      { media: "https://media.test/second.mp3", title: "Cell Party B", type: "audio" },
    ],
  });
});

test("video command delivers the completed generated video", async () => {
  const send: Fetch = async (input, init) => {
    const url = String(input);
    if (url.endsWith("/videos") && init?.method === "POST") {
      return new Response(JSON.stringify({
        id: "video-job-9",
        polling_url: "https://openrouter.ai/api/v1/videos/video-job-9",
        status: "pending",
      }), { headers: { "content-type": "application/json" } });
    }
    if (url === "https://media.test/video-job-9.mp4") {
      return new Response("generated-video", { headers: { "content-type": "video/mp4" } });
    }
    return new Response(JSON.stringify({
      id: "video-job-9",
      polling_url: "https://openrouter.ai/api/v1/videos/video-job-9",
      status: "completed",
      unsigned_urls: ["https://media.test/video-job-9.mp4"],
    }), { headers: { "content-type": "application/json" } });
  };
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database, fake } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    sentMessage(204),
    sentMessage(205),
    FakeBotApiReply.ok(true),
  ], config);
  await allow(database, "video");

  try {
    await app.run(bot.handler(commandUpdate("/video a corgi on a glassy wave", 2_004)));
  } finally {
    await app.close();
    database.close();
  }

  const video = fake.requests.find((request) => request.method === "sendVideo");
  expect(video?.contentType).toBe("multipart/form-data");
  expect(Object.values(video?.files ?? {})[0]?.size).toBe(15);
  expect(video?.params).toMatchObject({
    caption: expect.stringContaining("a corgi on a glassy wave"),
    chat_id: "-1007",
  });
});

test("video command downloads and frames a replied photo", async () => {
  const source = await sharp({
    create: { background: "red", channels: 3, height: 100, width: 100 },
  }).png().toBuffer();
  let submitted: Record<string, unknown> = {};
  const send: Fetch = async (input, init) => {
    const url = String(input);
    if (url.endsWith("/videos") && init?.method === "POST") {
      submitted = JSON.parse(String(init.body));
      return new Response(JSON.stringify({
        id: "video-image-job",
        polling_url: "https://openrouter.ai/api/v1/videos/video-image-job",
        status: "pending",
      }), { headers: { "content-type": "application/json" } });
    }
    if (url === "https://media.test/video-image-job.mp4") {
      return new Response("generated-video", { headers: { "content-type": "video/mp4" } });
    }
    return new Response(JSON.stringify({
      id: "video-image-job",
      polling_url: "https://openrouter.ai/api/v1/videos/video-image-job",
      status: "completed",
      unsigned_urls: ["https://media.test/video-image-job.mp4"],
    }), { headers: { "content-type": "application/json" } });
  };
  const config = {
    ...testConfig({ openrouterApiKey: "openrouter-test" }),
    admins: new Set<string>(),
  };
  const { app, bot, database } = await fixture(send, [
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok(true),
    FakeBotApiReply.ok({
      file_id: "photo-large",
      file_path: "photos/source.png",
      file_size: source.length,
      file_unique_id: "photo-unique",
    }),
    FakeBotApiReply.file(source),
    sentMessage(207),
    sentMessage(208),
    FakeBotApiReply.ok(true),
  ], config);
  await allow(database, "video");
  const base = commandUpdate("/video make it dance", 2_005);
  if (base.message === undefined) throw new Error("Expected video command");
  const update = {
    ...base,
    message: {
      ...base.message,
      replyToMessage: {
        chat: base.message.chat,
        date: base.message.date - 1,
        messageId: 2_004,
        photo: [{ fileId: "photo-large", fileSize: source.length, fileUniqueId: "photo-unique", height: 100, width: 100 }],
      },
    },
  };

  try {
    await app.run(bot.handler(update));
  } finally {
    await app.close();
    database.close();
  }

  expect(submitted).toMatchObject({ aspect_ratio: "1:1" });
  const frames = Reflect.get(submitted, "frame_images");
  expect(frames).toEqual([expect.objectContaining({ frame_type: "first_frame", type: "image_url" })]);
  expect(JSON.stringify(frames)).toContain("data:image/jpeg;base64,");
});
