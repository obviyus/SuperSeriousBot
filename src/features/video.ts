import * as Semaphore from "effect/Semaphore";
import sharp from "sharp";
import {
  deleteMessage,
  editMessageText,
  Effect,
  sendVideo,
} from "telly";

import { Ai, type AiError } from "../app/ai.ts";
import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { imageDataUrl, messageImage, type ImageData } from "../app/media.ts";

const videoLock = Semaphore.makeUnsafe(1);
const frames = [
  ["1:1", 480, 480],
  ["3:4", 480, 640],
  ["9:16", 480, 854],
  ["4:3", 640, 480],
  ["16:9", 854, 480],
  ["21:9", 1_120, 480],
] as const;

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
      return {
        aspectRatio: frame[0],
        firstFrame: imageDataUrl({ bytes, mimeType: "image/jpeg" }),
      };
    },
    catch: (error) => new Error(error instanceof Error ? error.message : String(error)),
  });
}

function failureText(error: AiError): string {
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
  const known = types.find(([type]) => error.description.includes(type))?.[1];
  return known === undefined
    ? "Video generation failed. Please try again."
    : `${known} No video job was created.`;
}

export function videoCommand(dependencies: AppDependencies): CommandDefinition {
  const ai = new Ai(dependencies);
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
        const bytes = yield* ai.video(match.argText, {
          aspectRatio: prepared?.aspectRatio ?? "16:9",
          ...(prepared === undefined ? {} : { firstFrame: prepared.firstFrame }),
        }).pipe(Effect.catch((error) => editMessageText({
          chatId: progress.chat.id,
          messageId: progress.messageId,
          text: failureText(error),
        }).pipe(Effect.as(undefined))));
        if (bytes === undefined) return;
        completed = true;
        const buffer = new ArrayBuffer(bytes.byteLength);
        new Uint8Array(buffer).set(bytes);
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
