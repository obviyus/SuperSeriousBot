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
  let submitted: Record<string, unknown> = {};
  const send: Fetch = async (input, init) => {
    const url = String(input);
    if (url.endsWith("/videos") && init?.method === "POST") {
      submitted = JSON.parse(String(init.body));
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
  await Effect.runPromise(database.execute(
    "INSERT INTO group_settings (chat_id, video_model) VALUES (-1, ?)",
    ["openrouter/bytedance/seedance-configured"],
  ));

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
  expect(submitted["model"]).toBe("bytedance/seedance-configured");
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
