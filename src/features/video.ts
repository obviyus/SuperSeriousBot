import * as Semaphore from "effect/Semaphore";
import sharp from "sharp";
import {
  deleteMessage,
  editMessageText,
  Effect,
  Schema,
  sendVideo,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { imageDataUrl, messageImage, type ImageData } from "../app/media.ts";

const SubmitVideo = Schema.Struct({ id: Schema.String });
const VideoStatus = Schema.Struct({ status: Schema.String });
const videoLock = Semaphore.makeUnsafe(1);
const frames = [
  ["1:1", 480, 480],
  ["3:4", 480, 640],
  ["9:16", 480, 854],
  ["4:3", 640, 480],
  ["16:9", 854, 480],
  ["21:9", 1_120, 480],
] as const;

function videoHeaders(dependencies: AppDependencies): HeadersInit {
  return {
    authorization: `Bearer ${dependencies.config.api.openrouterApiKey ?? ""}`,
    "content-type": "application/json",
    "http-referer": "https://superserio.us",
    "x-title": "SuperSeriousBot",
  };
}

function prepareImage(image: ImageData) {
  return Effect.tryPromise({
    try: async () => {
      const source = sharp(image.bytes).rotate();
      const metadata = await source.metadata();
      if (metadata.width === undefined || metadata.height === undefined) {
        throw new Error("Source image dimensions are missing");
      }
      const ratio = metadata.width / metadata.height;
      const frame = frames.reduce((best, candidate) => {
        const bestDistance = Math.abs(Math.log(ratio / (best[1] / best[2])));
        const candidateDistance = Math.abs(Math.log(ratio / (candidate[1] / candidate[2])));
        return candidateDistance < bestDistance ? candidate : best;
      });
      const bytes = await source.resize(frame[1], frame[2], {
        background: "black",
        fit: "contain",
      }).jpeg({ chromaSubsampling: "4:4:4", quality: 92 }).toBuffer();
      return { aspectRatio: frame[0], imageUrl: imageDataUrl({ bytes, mimeType: "image/jpeg" }) };
    },
    catch: (error) => new Error(error instanceof Error ? error.message : String(error)),
  });
}

function rejectionText(body: string): string {
  const types: ReadonlyArray<readonly [string, string]> = [
    ["InputImageSensitiveContentDetected.PrivacyInformation", "That image was rejected because it appears to contain a real person."],
    ["content_policy_violation", "The image or prompt was rejected by the video safety filter."],
    ["image_content_policy_violation", "The image or prompt was rejected by the video safety filter."],
    ["image_too_large", "That image is too large for video generation."],
    ["image_too_small", "That image is too small for video generation."],
    ["unsupported_image_format", "That image format cannot be used for video."],
    ["payment_required", "Video generation credits are unavailable."],
    ["rate_limit_exceeded", "The video service is busy. Try again shortly."],
  ];
  return `${types.find(([type]) => body.includes(type))?.[1] ?? "The video request was rejected before generation."} No video job was created.`;
}

export function videoCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    apiKey: "openrouterApiKey",
    availability: "whitelist",
    dailyLimit: 3,
    description: "Generate a five-second video with audio, or animate a replied image.",
    example: "/video A corgi surfs a glassy wave.",
    names: ["video"],
    run: Effect.fn("video")(function* (match) {
      if (match.argText.length === 0) return yield* usage(match.message, definition);
      const source = match.message.replyToMessage === undefined
        ? undefined
        : yield* messageImage(match.message.replyToMessage, true);
      const prepared = source === undefined ? undefined : yield* prepareImage(source);
      const progress = yield* answer(
        match.message,
        "Queued for a five-second video. Generation usually takes about two minutes.",
      );
      let completed = false;
      const program = Effect.gen(function* () {
        const response = yield* dependencies.http.response(
          "openrouter-video",
          "https://openrouter.ai/api/v1/videos",
          {
            body: JSON.stringify({
              aspect_ratio: prepared?.aspectRatio ?? "16:9",
              duration: 5,
              ...(prepared === undefined
                ? {}
                : {
                    frame_images: [{
                      frame_type: "first_frame",
                      image_url: { url: prepared.imageUrl },
                      type: "image_url",
                    }],
                  }),
              generate_audio: true,
              model: "bytedance/seedance-2.0-mini",
              prompt: match.argText,
              resolution: "480p",
            }),
            headers: videoHeaders(dependencies),
            method: "POST",
          },
        );
        const body = yield* Effect.tryPromise({
          try: () => response.text(),
          catch: () => new Error("Could not read video response"),
        });
        if (!response.ok) {
          yield* editMessageText({
            chatId: progress.chat.id,
            messageId: progress.messageId,
            text: rejectionText(body),
          });
          return;
        }
        const jobId = Schema.decodeUnknownSync(SubmitVideo)(JSON.parse(body)).id;
        for (let attempt = 0; attempt < 180; attempt += 1) {
          const status = yield* dependencies.http.json(
            "openrouter-video",
            `https://openrouter.ai/api/v1/videos/${encodeURIComponent(jobId)}`,
            VideoStatus,
            { headers: videoHeaders(dependencies) },
          );
          if (status.data.status === "completed") {
            completed = true;
            break;
          }
          if (status.data.status === "failed") return yield* Effect.die(
            new Error("OpenRouter video generation failed"),
          );
          if (!["pending", "in_progress"].includes(status.data.status)) {
            return yield* Effect.die(new Error("OpenRouter returned an invalid video status"));
          }
          yield* Effect.sleep("5 seconds");
        }
        if (!completed) return yield* Effect.die(new Error("Video generation timed out"));
        const video = yield* dependencies.http.bytes(
          "openrouter-video",
          `https://openrouter.ai/api/v1/videos/${encodeURIComponent(jobId)}/content`,
          50 * 1_024 * 1_024,
          { headers: videoHeaders(dependencies) },
        );
        const buffer = new ArrayBuffer(video.data.byteLength);
        new Uint8Array(buffer).set(video.data);
        const requester = match.message.from?.username === undefined
          ? `User ${match.message.from?.id ?? "unknown"}`
          : `@${match.message.from.username}`;
        const prompt = match.argText.length <= 850
          ? match.argText
          : `${match.argText.slice(0, 847)}...`;
        const delivered = yield* Effect.result(sendVideo({
          caption: `🎬 Requested by ${requester}\n📝 Prompt: ${prompt}`,
          chatId: match.message.chat.id,
          supportsStreaming: true,
          video: new File([buffer], "seedance.mp4", { type: "video/mp4" }),
        }));
        if (delivered._tag === "Failure") {
          yield* editMessageText({
            chatId: progress.chat.id,
            messageId: progress.messageId,
            text: "The video finished, but delivery failed. Don't retry yet; that could create a duplicate charge.",
          });
          return;
        }
        yield* deleteMessage({ chatId: progress.chat.id, messageId: progress.messageId });
      });
      yield* videoLock.withPermits(1)(program).pipe(Effect.catch(() => editMessageText({
        chatId: progress.chat.id,
        messageId: progress.messageId,
        text: completed
          ? "The video finished, but delivery failed. Don't retry yet; that could create a duplicate charge."
          : "Video generation failed. Please try again.",
      })));
    }),
    usage: "/video [prompt]",
  };
  return definition;
}
