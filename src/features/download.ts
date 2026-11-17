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
  describeError,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { mkdtemp, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";

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
      const file = new File([new Uint8Array(response.data)], name, {
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

async function run(command: ReadonlyArray<string>): Promise<{ readonly output: string; readonly errorOutput: string; readonly code: number }> {
  const child = Bun.spawn([...command], { env: process.env, stderr: "pipe", stdout: "pipe" });
  const [output, errorOutput] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
  ]);
  return { code: await child.exited, errorOutput, output };
}

// Telegram bots can upload at most 50 MB, so a longer video is re-encoded to
// fit: the bitrate is picked from the duration to land just under the cap.
async function fitVideo(path: string, directory: string): Promise<string> {
  if ((await stat(path)).size <= maximumBytes) return path;
  const probe = await run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]);
  const duration = Number(probe.output.trim());
  if (!Number.isFinite(duration) || duration <= 0) throw new Error("Video is too large and has no duration");
  const audioBitrate = 96_000;
  const videoBitrate = Math.floor((maximumBytes * 0.92 * 8) / duration) - audioBitrate;
  if (videoBitrate < 150_000) throw new Error("Video is too long to fit Telegram's upload limit");
  const output = join(directory, `${basename(path).replace(/\.[^.]+$/u, "")}_small.mp4`);
  const encode = await run([
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", path,
    "-c:v", "libx264", "-preset", "veryfast",
    "-b:v", String(videoBitrate), "-maxrate", String(videoBitrate), "-bufsize", String(videoBitrate * 2),
    "-vf", "scale=-2:min(1280\\,ih)",
    "-c:a", "aac", "-b:a", String(audioBitrate), "-movflags", "+faststart", output,
  ]);
  if (encode.code !== 0) throw new Error(`ffmpeg failed: ${encode.errorOutput.trim().slice(0, 300)}`);
  if ((await stat(output)).size > maximumBytes) throw new Error("Video is still too large after re-encoding");
  return output;
}

function ytDlp(message: Message, url: URL) {
  return Effect.acquireUseRelease(
    Effect.promise(() => mkdtemp(join(tmpdir(), "ssb-dl-"))),
    (directory) => Effect.tryPromise({
      try: async () => {
        const result = await run([
          "yt-dlp",
          "--no-playlist",
          "--quiet",
          "--format",
          "best[ext=mp4]/bv*+ba/b",
          "--merge-output-format",
          "mp4",
          "--output",
          join(directory, "%(id)s.%(ext)s"),
          "--print",
          "after_move:filepath",
          url.toString(),
        ]);
        if (result.code !== 0) {
          const reason = result.errorOutput.trim().split("\n").findLast((line) => line.startsWith("ERROR:"));
          throw new Error(`yt-dlp failed: ${(reason ?? result.errorOutput.trim()).slice(0, 500)}`);
        }
        const downloaded = result.output.trim().split("\n").at(-1);
        if (downloaded === undefined || downloaded === "") throw new Error("yt-dlp returned no file");
        const path = await fitVideo(downloaded, directory);
        return new File([await Bun.file(path).arrayBuffer()], basename(path), { type: "video/mp4" });
      },
      catch: (error) => error instanceof Error ? error : new Error(`yt-dlp failed: ${String(error)}`),
    }).pipe(Effect.flatMap((video) =>
      sendVideo({ ...respondTo(message), supportsStreaming: true, video }).pipe(Effect.asVoid)
    )),
    (directory) => Effect.promise(() => rm(directory, { force: true, recursive: true })),
  );
}

// Every way Cobalt can fail (an error status, the wrong media, a failed
// request) goes through here, so Instagram always gets its fallback.
function fallback(dependencies: AppDependencies, message: Message, target: URL, reason: string) {
  if (instagram(target, "reel")) return ytDlp(message, target);
  if (instagram(target, "p")) return instagramPage(dependencies, message, target);
  return answer(message, reason).pipe(Effect.asVoid);
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
          ? Effect.succeed("Failed to fetch media.")
          : sendBytes(dependencies, message, data.url, data.filename).pipe(Effect.as(undefined));
      }
      if (data.status === "picker") {
        const media = (data.picker ?? []).slice(0, 10).filter((item) => item.url !== undefined);
        return media.length === 0
          ? answer(message, "No media found.").pipe(Effect.as(undefined))
          : Effect.forEach(media, (item) => {
              const url = item.url;
              if (url === undefined) return Effect.void;
              return item.type === "photo" || imageExtensions.some((extension) => url.endsWith(extension))
                ? sendPhoto({ ...respondTo(message), photo: url }).pipe(Effect.asVoid)
                : sendVideo({ ...respondTo(message), video: url }).pipe(Effect.asVoid);
            }, { concurrency: 1, discard: true }).pipe(Effect.as(undefined));
      }
      return Effect.succeed(data.status === "error"
        ? `Failed to fetch media: ${data.error?.code ?? "unknown"}`
        : "Download service returned an unsupported response.");
    }),
    // A failure here, including media too large to send, falls back once.
    // The fallback's own failure is the command's error, not retried.
    Effect.catch(() => Effect.succeed("Failed to fetch media.")),
    Effect.flatMap((reason) => reason === undefined ? Effect.void : fallback(dependencies, message, target, reason)),
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
  }, Effect.catch((error) => Effect.logError("Automatic download failed").pipe(
    Effect.annotateLogs({ error: describeError(error) }),
  )));
  return { commands: [command] as const, handler };
}
