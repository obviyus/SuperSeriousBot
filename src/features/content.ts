import {
  downloadFile,
  Effect,
  messageEntities,
  messageMedia,
  Schema,
  type Message,
} from "telly";

import { Ai } from "../app/ai.ts";
import { transcodeToWav } from "../app/audio.ts";
import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { replyMarkdownOrPlain } from "../app/markdown.ts";

const TranscriptResponse = Schema.Struct({
  transcripts: Schema.Array(Schema.Struct({
    transcript: Schema.optionalKey(Schema.String),
  })),
});
const ScrapeResponse = Schema.Struct({
  results: Schema.Array(Schema.Struct({
    content: Schema.optionalKey(Schema.String),
    error: Schema.optionalKey(Schema.String),
    markdown: Schema.optionalKey(Schema.String),
    success: Schema.Boolean,
  })),
});

function firstLink(message: Message): URL | undefined {
  for (const span of messageEntities(message, "url", "text_link")) {
    const value = span.entity.url ?? span.text;
    if (URL.canParse(value)) return new URL(value);
  }
  return message.replyToMessage === undefined ? undefined : firstLink(message.replyToMessage);
}

export function youtubeVideoId(url: URL): string | undefined {
  const host = url.hostname.replace(/^www\./u, "");
  if (host === "youtu.be") return url.pathname.slice(1).split("/", 1)[0] || undefined;
  if (!new Set([
    "youtube.com",
    "m.youtube.com",
    "youtube-nocookie.com",
    "music.youtube.com",
    "gaming.youtube.com",
  ]).has(host)) return undefined;
  if (url.pathname === "/watch" || url.pathname === "/watch_popup") {
    return url.searchParams.get("v") ?? undefined;
  }
  const match = url.pathname.match(/^\/(?:embed|v|shorts)\/([^/]+)/u);
  return match?.[1];
}

function summarize(ai: Ai, text: string, context: string) {
  return ai.complete("tldr", [
    {
      content: `Summarize the content${context.length === 0 ? "" : ` (${context})`} in 3-6 concise bullet points. Return only the bullets.`,
      role: "system",
    },
    { content: text.slice(0, 20_000), role: "user" },
  ], { maxTokens: 500 });
}

function tldrCommand(dependencies: AppDependencies, ai: Ai): CommandDefinition {
  const definition: CommandDefinition = {
    apiKey: "openrouterApiKey",
    availability: "whitelist",
    dailyLimit: 30,
    description: "Summarize a URL, YouTube video, replied message, or text file.",
    example: "/tldr",
    names: ["tldr", "tldw"],
    run: Effect.fn("tldr")(function* (match) {
      const url = firstLink(match.message);
      if (url !== undefined) {
        const videoId = youtubeVideoId(url);
        if (videoId !== undefined) {
          const cached = yield* dependencies.database.one(
            "SELECT summary FROM tldw WHERE video_id = ? ORDER BY id DESC LIMIT 1",
            [videoId],
          );
          if (cached !== undefined) {
            return yield* replyMarkdownOrPlain(match.message, rowString(cached, "summary"));
          }
          const response = yield* dependencies.http.json(
            "nano-gpt-youtube",
            "https://nano-gpt.com/api/youtube-transcribe",
            TranscriptResponse,
            {
              body: JSON.stringify({ urls: [`https://www.youtube.com/watch?v=${videoId}`] }),
              headers: {
                "content-type": "application/json",
                ...(dependencies.config.api.nanoGptApiKey === undefined
                  ? {}
                  : { "x-api-key": dependencies.config.api.nanoGptApiKey }),
              },
              method: "POST",
            },
          ).pipe(Effect.catch(() => Effect.succeed(undefined)));
          const transcript = response?.data.transcripts[0]?.transcript;
          if (response?.status !== 200 || transcript === undefined) {
            return yield* answer(match.message, "Could not retrieve transcript for this video.");
          }
          const summary = yield* summarize(ai, `YouTube transcript:\n\n${transcript}`, "a YouTube transcript");
          yield* dependencies.database.execute(
            "INSERT INTO tldw (video_id, summary, user_id) VALUES (?, ?, ?)",
            [videoId, summary, match.message.from?.id ?? 0],
          );
          return yield* replyMarkdownOrPlain(match.message, summary);
        }
        const response = yield* dependencies.http.json(
          "nano-gpt-scrape",
          "https://nano-gpt.com/api/scrape-urls",
          ScrapeResponse,
          {
            body: JSON.stringify({ urls: [url.toString()] }),
            headers: {
              "content-type": "application/json",
              ...(dependencies.config.api.nanoGptApiKey === undefined
                ? {}
                : { "x-api-key": dependencies.config.api.nanoGptApiKey }),
            },
            method: "POST",
          },
        ).pipe(Effect.catch(() => Effect.succeed(undefined)));
        const result = response?.data.results[0];
        const source = result?.markdown ?? result?.content;
        if (response?.status !== 200 || result?.success !== true || source === undefined) {
          return yield* answer(match.message, "I couldn't read that URL.");
        }
        const summary = yield* summarize(ai, source, "a web page");
        return yield* replyMarkdownOrPlain(
          match.message,
          `${summary}\n\nSource: ${url}`,
          { linkPreviewDisabled: true },
        );
      }
      const replied = match.message.replyToMessage;
      if (replied === undefined) return yield* usage(match.message, definition);
      if (replied.document !== undefined) {
        if ((replied.document.fileSize ?? 0) > 2_000_000) {
          return yield* answer(match.message, "That file is too big to summarize.");
        }
        const bytes = yield* downloadFile({ fileId: replied.document.fileId });
        const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        if (text.trim().length === 0) return yield* answer(match.message, "That file is empty.");
        const summary = yield* summarize(ai, text, `file ${replied.document.fileName ?? "document"}`);
        return yield* replyMarkdownOrPlain(match.message, summary);
      }
      const text = replied.text ?? replied.caption;
      if (text === undefined) return yield* usage(match.message, definition);
      const summary = yield* summarize(ai, text, "a replied message");
      return yield* replyMarkdownOrPlain(match.message, summary);
    }),
    usage: "/tldr with a URL, or reply to text or a text file",
  };
  return definition;
}

function transcribeCommand(ai: Ai): CommandDefinition {
  const definition: CommandDefinition = {
    apiKey: "openrouterApiKey",
    availability: "whitelist",
    dailyLimit: 40,
    description: "Reply to an audio message to transcribe it with AI.",
    example: "/tr Please summarize with bullet points",
    names: ["tr"],
    run: Effect.fn("transcribe")(function* (match) {
      const replied = match.message.replyToMessage;
      const media = replied === undefined ? undefined : messageMedia(replied);
      const audio = media?.type === "voice"
        ? { fileId: media.voice.fileId, mimeType: media.voice.mimeType ?? "audio/ogg", source: "voice message" }
        : media?.type === "audio"
        ? { fileId: media.audio.fileId, mimeType: media.audio.mimeType ?? "audio/mpeg", source: "audio file" }
        : media?.type === "document" && media.document.mimeType?.startsWith("audio/") === true
        ? { fileId: media.document.fileId, mimeType: media.document.mimeType, source: "audio document" }
        : undefined;
      if (audio === undefined) return yield* usage(match.message, definition);
      const bytes = yield* downloadFile({ fileId: audio.fileId });
      const extension = audio.mimeType.includes("mpeg") ? ".mp3" : ".ogg";
      const wav = yield* transcodeToWav(bytes, extension).pipe(
        Effect.catch(() => answer(match.message, "I couldn't process that audio.").pipe(
          Effect.as(undefined),
        )),
      );
      if (wav === undefined) return;
      const instruction = match.argText.length === 0
        ? "Transcribe this audio. Begin immediately without commentary and keep it readable for Telegram."
        : match.argText;
      const transcript = yield* ai.complete("tr", [{
        content: [
          { text: `You are transcribing a ${audio.source}. ${instruction}`, type: "text" },
          {
            data: wav,
            mediaType: "audio/wav",
            type: "file",
          },
        ],
        role: "user",
      }]).pipe(Effect.catch(() => answer(
        match.message,
        "Transcription failed. Please try again.",
      ).pipe(Effect.as(undefined))));
      if (transcript === undefined) return;
      if (transcript.trim().length === 0) {
        return yield* answer(match.message, "No transcript was returned. Please try again.");
      }
      yield* replyMarkdownOrPlain(match.message, transcript.trim(), {
        documentName: "transcript.txt",
        linkPreviewDisabled: true,
      });
    }),
    usage: "/tr [optional instructions] as a reply to audio",
  };
  return definition;
}

export function contentCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  const ai = new Ai(dependencies);
  return [tldrCommand(dependencies, ai), transcribeCommand(ai)];
}
