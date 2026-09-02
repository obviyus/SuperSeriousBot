import {
  Effect,
  messageEntities,
  respondTo,
  Schema,
  sendDocument,
  sendPhoto,
  sendVideo,
  setMessageReaction,
  type Message,
  type UpdateHandler,
} from "telly";

import {
  answer,
  type CommandDefinition,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const maximumBytes = 47 * 1_024 * 1_024;
const imageExtensions = [".jpg", ".jpeg", ".png", ".webp", ".gif"];
const videoExtensions = [".mp4", ".mov", ".webm", ".mkv", ".avi"];
const CobaltResponse = Schema.Struct({
  audio: Schema.optionalKey(Schema.String),
  error: Schema.optionalKey(Schema.Struct({ code: Schema.optionalKey(Schema.String) })),
  filename: Schema.optionalKey(Schema.String),
  picker: Schema.optionalKey(Schema.Array(Schema.Struct({
    type: Schema.optionalKey(Schema.String),
    url: Schema.optionalKey(Schema.String),
  }))),
  status: Schema.String,
  url: Schema.optionalKey(Schema.String),
});

function links(message: Message): ReadonlyArray<URL> {
  return messageEntities(message, "url", "text_link").flatMap((span) => {
    const value = span.entity.url ?? span.text;
    return URL.canParse(value) ? [new URL(value)] : [];
  });
}

function firstLink(message: Message): URL | undefined {
  return links(message)[0] ?? (message.replyToMessage === undefined
    ? undefined
    : links(message.replyToMessage)[0]);
}

function instagram(url: URL, path: "p" | "reel"): boolean {
  return ["instagram.com", "www.instagram.com"].includes(url.hostname) &&
    url.pathname.startsWith(`/${path}/`);
}

function sendBytes(
  dependencies: AppDependencies,
  message: Message,
  url: string,
  fileName?: string,
) {
  return dependencies.http.bytes("media-download", url, maximumBytes).pipe(
    Effect.flatMap((response) => {
      if (response.status !== 200) return Effect.fail(new Error("Media download failed"));
      const name = fileName ?? response.fileName ?? "file";
      const buffer = new ArrayBuffer(response.data.byteLength);
      new Uint8Array(buffer).set(response.data);
      const file = new File([buffer], name, {
        type: response.contentType ?? "application/octet-stream",
      });
      const lower = name.toLowerCase();
      if (imageExtensions.some((extension) => lower.endsWith(extension)) ||
        response.contentType?.startsWith("image/") === true) {
        return sendPhoto({ ...respondTo(message), photo: file }).pipe(Effect.asVoid);
      }
      if (videoExtensions.some((extension) => lower.endsWith(extension)) ||
        response.contentType?.startsWith("video/") === true) {
        return sendVideo({ ...respondTo(message), supportsStreaming: true, video: file }).pipe(
          Effect.asVoid,
        );
      }
      return sendDocument({ ...respondTo(message), document: file }).pipe(Effect.asVoid);
    }),
  );
}

function instagramPage(dependencies: AppDependencies, message: Message, url: URL) {
  return dependencies.http.text("instagram", url, {
    headers: { "user-agent": "Mozilla/5.0" },
  }).pipe(
    Effect.flatMap((response) => {
      const media = response.data.match(/<meta[^>]+property=["']og:(?:video|image)["'][^>]+content=["']([^"']+)["']/iu)?.[1];
      if (media === undefined) return Effect.fail(new Error("Instagram has no media metadata"));
      const shortcode = url.pathname.split("/").filter(Boolean).at(-1) ?? "post";
      return sendBytes(dependencies, message, media.replaceAll("&amp;", "&"), `instagram_${shortcode}.jpg`);
    }),
  );
}

function ytDlp(dependencies: AppDependencies, message: Message, url: URL) {
  return Effect.tryPromise({
    try: async () => {
      const process = Bun.spawn([
        "yt-dlp",
        "--no-playlist",
        "--format",
        "best[ext=mp4]/best",
        "--print",
        "after_move:filepath",
        "--get-url",
        url.toString(),
      ], { stderr: "pipe", stdout: "pipe" });
      const output = await new Response(process.stdout).text();
      if (await process.exited !== 0) throw new Error("yt-dlp failed");
      const [mediaUrl, fileName] = output.trim().split("\n");
      if (mediaUrl === undefined) throw new Error("yt-dlp returned no media URL");
      return { fileName, mediaUrl };
    },
    catch: () => new Error("yt-dlp failed"),
  }).pipe(Effect.flatMap(({ fileName, mediaUrl }) => sendBytes(
    dependencies,
    message,
    mediaUrl,
    fileName,
  )));
}

function download(dependencies: AppDependencies, message: Message, target: URL) {
  const base = dependencies.config.api.cobaltUrl;
  if (base === undefined) return answer(message, "Download service is not configured.");
  return dependencies.http.json(
    "cobalt",
    `${base.replace(/\/+$/u, "")}/`,
    CobaltResponse,
    {
      body: JSON.stringify({ url: target.toString() }),
      headers: { accept: "application/json", "content-type": "application/json" },
      method: "POST",
    },
  ).pipe(
    Effect.flatMap((response) => {
      const data = response.data;
      if (["redirect", "tunnel"].includes(data.status) && data.url !== undefined) {
        const wrongReelMedia = instagram(target, "reel") && data.filename !== undefined &&
          imageExtensions.some((extension) => data.filename?.toLowerCase().endsWith(extension));
        return wrongReelMedia
          ? ytDlp(dependencies, message, target)
          : sendBytes(dependencies, message, data.url, data.filename);
      }
      if (data.status === "picker") {
        const media = (data.picker ?? []).slice(0, 10).filter((item) => item.url !== undefined);
        return media.length === 0
          ? answer(message, "No media found.").pipe(Effect.asVoid)
          : Effect.forEach(media, (item) => {
              const url = item.url;
              if (url === undefined) return Effect.void;
              return item.type === "photo" || imageExtensions.some((extension) => url.endsWith(extension))
                ? sendPhoto({ ...respondTo(message), photo: url }).pipe(Effect.asVoid)
                : sendVideo({ ...respondTo(message), video: url }).pipe(Effect.asVoid);
            }, { concurrency: 1, discard: true });
      }
      if (data.status === "error" && instagram(target, "p")) {
        return instagramPage(dependencies, message, target);
      }
      return answer(
        message,
        data.status === "error"
          ? `Failed to fetch media: ${data.error?.code ?? "unknown"}`
          : "Download service returned an unsupported response.",
      ).pipe(Effect.asVoid);
    }),
    Effect.catch(() => {
      if (instagram(target, "reel")) return ytDlp(dependencies, message, target);
      if (instagram(target, "p")) return instagramPage(dependencies, message, target);
      return answer(message, "Failed to fetch media.");
    }),
    Effect.asVoid,
  );
}

export function downloadFeature(dependencies: AppDependencies) {
  const command: CommandDefinition = {
    description: "Download media through a Cobalt-compatible service.",
    example: "/dl https://www.instagram.com/reel/A1234567890/",
    names: ["dl"],
    run: Effect.fn("download")(function* (match) {
      const target = firstLink(match.message);
      if (target === undefined) return yield* answer(match.message, "Please provide a valid URL.");
      yield* download(dependencies, match.message, target);
    }),
    usage: "/dl [URL]",
  };
  const handler: UpdateHandler<never, void> = Effect.fn("autoDownload")(function* (update) {
    const message = update.message;
    if (
      message?.text === undefined ||
      message.from?.isBot !== false ||
      message.chat.type === "private"
    ) return;
    const setting = yield* dependencies.database.one(
      "SELECT auto_dl FROM group_settings WHERE chat_id = ?",
      [message.chat.id],
    );
    if (setting?.["auto_dl"] !== 1) return;
    const target = links(message).find((url) => instagram(url, "reel"));
    if (target === undefined) return;
    yield* setMessageReaction({
      chatId: message.chat.id,
      messageId: message.messageId,
      reaction: [{ emoji: "⚡", type: "emoji" }],
    }).pipe(Effect.catch(() => Effect.void));
    yield* download(dependencies, message, target);
  }, Effect.catch(() => Effect.logError("Automatic download failed")));
  return { commands: [command] as const, handler };
}
