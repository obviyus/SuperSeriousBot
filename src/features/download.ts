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
  CommandFailure,
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

// Embed-fixer mirrors (fxtwitter and friends) rewrite links so chats show a
// preview. Cobalt only knows the real sites, so links are mapped back first.
const mirrors: ReadonlyArray<readonly [ReadonlyArray<string>, string]> = [
  [["fxtwitter.com", "vxtwitter.com", "fixupx.com", "fixvx.com", "twittpr.com", "stupidpenisx.com", "girlcockx.com"], "x.com"],
  [["ddinstagram.com", "kkinstagram.com", "uuinstagram.com", "instagramez.com", "d.ddinstagram.com"], "www.instagram.com"],
  [["vxreddit.com", "rxddit.com", "rxyddit.com"], "www.reddit.com"],
  [["vxtiktok.com", "tnktok.com", "tiktxk.com", "tfxktok.com"], "www.tiktok.com"],
  [["fxbsky.app", "bskyx.app", "bskye.app"], "bsky.app"],
];

export function canonicalLink(url: URL): URL {
  const host = url.hostname.toLowerCase();
  const site = mirrors.find(([hosts]) => hosts.some((mirror) => host === mirror || host.endsWith(`.${mirror}`)))?.[1];
  if (site === undefined) return url;
  const canonical = new URL(url);
  canonical.hostname = site;
  return canonical;
}

function links(message: Message): ReadonlyArray<URL> {
  return messageEntities(message, "url", "text_link").flatMap((span) => {
    const value = span.entity.url ?? span.text;
    return URL.canParse(value) ? [canonicalLink(new URL(value))] : [];
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

// Telegram bot uploads: photos up to 10 MB, anything else up to 50 MB.
const photoBytes = 10 * 1_024 * 1_024;
// Downloads beyond this are refused before re-encoding, to protect the disk.
const sourceBytes = 400 * 1_024 * 1_024;

interface Media {
  readonly path: string;
  readonly kind: "photo" | "video" | "document";
}

function kindOf(name: string, contentType: string | undefined): Media["kind"] {
  const lower = name.toLowerCase();
  if (contentType?.startsWith("image/") === true || imageExtensions.some((extension) => lower.endsWith(extension))) return "photo";
  if (contentType?.startsWith("video/") === true || videoExtensions.some((extension) => lower.endsWith(extension))) return "video";
  return "document";
}

async function run(command: ReadonlyArray<string>): Promise<{ readonly output: string; readonly errorOutput: string; readonly code: number }> {
  const child = Bun.spawn([...command], { env: process.env, stderr: "pipe", stdout: "pipe" });
  const [output, errorOutput] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
  ]);
  return { code: await child.exited, errorOutput, output };
}

// Streams a media URL to disk, refusing anything over sourceBytes.
async function fetchToFile(
  dependencies: Pick<AppDependencies, "config" | "http">,
  url: string,
  directory: string,
  index: number,
  fileName?: string,
): Promise<Media> {
  const response = await dependencies.http.fetch(url, { signal: AbortSignal.timeout(300_000) });
  if (!response.ok || response.body === null) throw new Error(`media download returned ${response.status}`);
  if (Number(response.headers.get("content-length") ?? 0) > sourceBytes) throw new Error("media is over 400 MB");
  const contentType = response.headers.get("content-type") ?? undefined;
  const disposition = response.headers.get("content-disposition")?.match(/filename\*?=(?:UTF-8''|["']?)([^"';]+)/iu)?.[1];
  const name = basename(fileName ?? (disposition === undefined ? undefined : decodeURIComponent(disposition)) ??
    (new URL(url).pathname.split("/").at(-1) || "file"));
  const path = join(directory, `${index}-${name}`);
  const writer = Bun.file(path).writer();
  let size = 0;
  try {
    for await (const chunk of response.body) {
      size += chunk.byteLength;
      if (size > sourceBytes) throw new Error("media is over 400 MB");
      writer.write(chunk);
    }
  } finally {
    await writer.end();
  }
  return { kind: kindOf(name, contentType), path };
}

// Telegram bots can upload at most 50 MB, so a longer video is re-encoded to
// fit: the bitrate is picked from the duration to land just under the cap.
async function fitVideo(path: string, directory: string): Promise<string> {
  if ((await stat(path)).size <= maximumBytes) return path;
  const probe = await run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]);
  const duration = Number(probe.output.trim());
  if (!Number.isFinite(duration) || duration <= 0) throw new Error("video is too large and has no duration");
  const audioBitrate = 96_000;
  const videoBitrate = Math.floor((maximumBytes * 0.92 * 8) / duration) - audioBitrate;
  if (videoBitrate < 150_000) throw new Error("video is too long to fit Telegram's upload limit");
  const output = join(directory, `${basename(path).replace(/\.[^.]+$/u, "")}_small.mp4`);
  const encode = await run([
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", path,
    "-c:v", "libx264", "-preset", "veryfast",
    "-b:v", String(videoBitrate), "-maxrate", String(videoBitrate), "-bufsize", String(videoBitrate * 2),
    "-vf", "scale=-2:min(1280\\,ih)",
    "-c:a", "aac", "-b:a", String(audioBitrate), "-movflags", "+faststart", output,
  ]);
  if (encode.code !== 0) throw new Error(`ffmpeg failed: ${encode.errorOutput.trim().slice(0, 300)}`);
  if ((await stat(output)).size > maximumBytes) throw new Error("video is still too large after re-encoding");
  return output;
}

// Makes every file sendable: videos are shrunk, big photos go as documents,
// and anything still over Telegram's limit fails so the next source runs.
async function prepare(media: Media, directory: string): Promise<Media> {
  if (media.kind === "video") return { kind: "video", path: await fitVideo(media.path, directory) };
  const size = (await stat(media.path)).size;
  if (media.kind === "photo" && size <= photoBytes) return media;
  if (size > maximumBytes) throw new Error("file is over Telegram's 50 MB limit");
  return { kind: "document", path: media.path };
}

type Source = (dependencies: Pick<AppDependencies, "config" | "http">, target: URL, directory: string) => Promise<ReadonlyArray<Media>>;

const cobalt: Source = async (dependencies, target, directory) => {
  const base = dependencies.config.api.cobaltUrl;
  if (base === undefined) throw new Error("not configured");
  const response = await dependencies.http.fetch(`${base.replace(/\/+$/u, "")}/`, {
    body: JSON.stringify({ url: target.toString() }),
    headers: { accept: "application/json", "content-type": "application/json" },
    method: "POST",
    signal: AbortSignal.timeout(60_000),
  });
  const data = Schema.decodeUnknownSync(CobaltResponse)(await response.json());
  if (["redirect", "tunnel"].includes(data.status) && data.url !== undefined) {
    const media = await fetchToFile(dependencies, data.url, directory, 0, data.filename);
    // Cobalt sometimes answers a reel with its cover image.
    if (instagram(target, "reel") && media.kind === "photo") throw new Error("returned an image for a reel");
    return [media];
  }
  if (data.status === "picker") {
    const items = (data.picker ?? []).flatMap((item) => item.url === undefined ? [] : [item]).slice(0, 10);
    if (items.length === 0) throw new Error("picker had no media");
    return Promise.all(items.map(async (item, index) => {
      const media = await fetchToFile(dependencies, item.url!, directory, index);
      return item.type === "photo" && media.kind === "document" ? { ...media, kind: "photo" as const } : media;
    }));
  }
  throw new Error(data.status === "error" ? (data.error?.code ?? "error") : `unsupported status ${data.status}`);
};

const ytDlp: Source = async (_dependencies, target, directory) => {
  const result = await run([
    "yt-dlp",
    "--no-playlist",
    "--quiet",
    "--max-filesize", String(sourceBytes),
    "--format", "best[ext=mp4]/bv*+ba/b",
    "--merge-output-format", "mp4",
    "--output", join(directory, "%(id)s.%(ext)s"),
    "--print", "after_move:filepath",
    target.toString(),
  ]);
  if (result.code !== 0) {
    const reason = result.errorOutput.trim().split("\n").findLast((line) => line.startsWith("ERROR:"));
    throw new Error((reason ?? result.errorOutput.trim()).slice(0, 500));
  }
  const path = result.output.trim().split("\n").at(-1);
  if (path === undefined || path === "") throw new Error("returned no file");
  return [{ kind: kindOf(path, undefined) === "photo" ? "photo" : "video", path }];
};

const instagramPage: Source = async (dependencies, target, directory) => {
  if (!instagram(target, "p")) throw new Error("only for Instagram posts");
  const response = await dependencies.http.fetch(target, { headers: { "user-agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(60_000) });
  const page = await response.text();
  const media = page.match(/<meta[^>]+property=["']og:(?:video|image)["'][^>]+content=["']([^"']+)["']/iu)?.[1];
  if (media === undefined) throw new Error("no media metadata");
  const shortcode = target.pathname.split("/").filter(Boolean).at(-1) ?? "post";
  return [await fetchToFile(dependencies, media.replaceAll("&amp;", "&"), directory, 0, `instagram_${shortcode}.jpg`)];
};

// Every link goes through every source in order, and every file goes through
// the same preparation, so one source breaking never reaches the chat while
// another still works. Only when all fail does the command fail, with each
// source's reason recorded.
const sources: ReadonlyArray<readonly [string, Source]> = [["Cobalt", cobalt], ["yt-dlp", ytDlp], ["Instagram page", instagramPage]];

export async function resolveMedia(dependencies: Pick<AppDependencies, "config" | "http">, target: URL, directory: string): Promise<ReadonlyArray<Media>> {
  const reasons: Array<string> = [];
  for (const [name, source] of sources) {
    if (name === "Instagram page" && !instagram(target, "p")) continue;
    try {
      const media = await source(dependencies, target, directory);
      return await Promise.all(media.map((item) => prepare(item, directory)));
    } catch (error) {
      reasons.push(`${name}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  throw new CommandFailure("Couldn't download media from that link.", `Download failed. ${reasons.join("; ")}`);
}

function download(dependencies: AppDependencies, message: Message, target: URL) {
  return Effect.acquireUseRelease(
    Effect.promise(() => mkdtemp(join(tmpdir(), "ssb-dl-"))),
    (directory) => Effect.tryPromise({
      try: () => resolveMedia(dependencies, target, directory),
      catch: (error) => error instanceof Error ? error : new Error(String(error)),
    }).pipe(
      Effect.flatMap((media) => Effect.forEach(media, (item) => Effect.promise(async () =>
        new File([await Bun.file(item.path).arrayBuffer()], basename(item.path).replace(/^\d+-/u, ""), {
          type: item.kind === "video" ? "video/mp4" : Bun.file(item.path).type,
        })
      ).pipe(Effect.flatMap((file) => item.kind === "photo"
        ? sendPhoto({ ...respondTo(message), photo: file })
        : item.kind === "video"
        ? sendVideo({ ...respondTo(message), supportsStreaming: true, video: file })
        : sendDocument({ ...respondTo(message), document: file }))), { concurrency: 1, discard: true })),
    ),
    (directory) => Effect.promise(() => rm(directory, { force: true, recursive: true })),
  );
}

export function downloadFeature(dependencies: AppDependencies) {
  const command: CommandDefinition = {
    description: "Download media from a link through Cobalt, then yt-dlp.",
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
