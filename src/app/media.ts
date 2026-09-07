import {
  downloadFile,
  Effect,
  messageMedia,
  type Bot,
  type BotApiError,
  type Message,
} from "telly";

export interface ImageData {
  readonly bytes: Uint8Array;
  readonly mimeType: string;
}

export function messageImage(
  message: Message,
  allowDocument = false,
): Effect.Effect<ImageData | undefined, BotApiError, Bot> {
  const media = messageMedia(message);
  if (media?.type === "photo") {
    return downloadFile({ fileId: media.photo.fileId }).pipe(
      Effect.map((bytes) => ({ bytes, mimeType: "image/jpeg" })),
    );
  }
  if (media?.type === "sticker") {
    if (media.sticker.isAnimated || media.sticker.isVideo) {
      return Effect.die(new Error(
        "Animated/video stickers aren't supported yet. Send a static sticker or image.",
      ));
    }
    return downloadFile({ fileId: media.sticker.fileId }).pipe(
      Effect.map((bytes) => ({ bytes, mimeType: "image/webp" })),
    );
  }
  if (
    allowDocument &&
    media?.type === "document" &&
    media.document.mimeType?.startsWith("image/") === true
  ) {
    const mimeType = media.document.mimeType;
    return downloadFile({ fileId: media.document.fileId }).pipe(
      Effect.map((bytes) => ({ bytes, mimeType })),
    );
  }
  return Effect.succeed(undefined);
}

export function imageDataUrl(image: ImageData): string {
  return `data:${image.mimeType};base64,${Buffer.from(image.bytes).toString("base64")}`;
}
