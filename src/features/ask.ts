import {
  editMessageText,
  Effect,
  sendPhoto,
  type Message,
} from "telly";

import { Ai, streamChunk, type AiMessage } from "../app/ai.ts";
import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { messageImage } from "../app/media.ts";
import {
  editRich,
  richMarkdownPrompt,
  richMessageLimit,
} from "../app/rich.ts";

const plainPreviewLimit = 4_096;
const wordLimit = 1_000;
const systemPrompt = `You are @SuperSeriousBot in a Telegram chat. Be extremely concise.

Answer directly in one or two short paragraphs under 100 words. Skip introductions, summaries, warnings, and filler. Use lists only when asked.`;

function streamCutoff(group: boolean, length: number): number {
  if (length > 1_000) return group ? 180 : 90;
  if (length > 200) return group ? 120 : 45;
  if (length > 50) return group ? 90 : 25;
  return group ? 50 : 15;
}

function words(text: string): number {
  return text.trim().split(/\s+/u).filter(Boolean).length;
}

function askCommand(dependencies: AppDependencies, ai: Ai): CommandDefinition {
  const definition: CommandDefinition = {
    apiKey: "openrouterApiKey",
    availability: "whitelist-private",
    dailyLimit: 40,
    description: "Ask anything. Reply to text, an image, or a static sticker for context.",
    example: "/ask How long does a train between Tokyo and Hokkaido take?",
    names: ["ask"],
    run: Effect.fn("ask")(function* (match) {
      let query = match.argText;
      const replied = match.message.replyToMessage;
      const replyContext = replied?.text ?? replied?.caption;
      if (words(query) > wordLimit) {
        return yield* answer(match.message, `Please keep your query under ${wordLimit} words.`);
      }
      if (replyContext !== undefined && words(replyContext) > wordLimit) {
        return yield* answer(match.message, `Please reply to a message under ${wordLimit} words.`);
      }
      const image = replied === undefined ? undefined : yield* messageImage(replied);
      const messages: Array<AiMessage> = [
        { content: systemPrompt, role: "system" },
        { content: richMarkdownPrompt, role: "system" },
      ];
      if (image !== undefined) {
        const prompt = query.length === 0 ? "Describe this image in detail." : query;
        messages.push({
          content: [
            { text: replyContext === undefined
              ? prompt
              : `Reply context:\n${replyContext}\n\nUser request:\n${prompt}`, type: "text" },
            { data: image.bytes, mediaType: image.mimeType, type: "file" },
          ],
          role: "user",
        });
      } else {
        if (query.length === 0) return yield* usage(match.message, definition);
        if (replyContext !== undefined) {
          query = `Reply context:\n${replyContext}\n\nUser request:\n${query}`;
        }
        messages.push({ content: query, role: "user" });
      }
      const stream = yield* ai.stream("ask", messages);
      return yield* Effect.gen(function* () {
        let content = "";
        let sent: Message | undefined;
        let lastLength = 0;
        let lastEdit = 0;
        while (true) {
          const next = yield* streamChunk(stream);
          if (next.done) break;
          content = `${content}${next.value}`.slice(0, richMessageLimit);
          if (content.length === 0) continue;
          const preview = content.slice(0, plainPreviewLimit);
          if (sent === undefined) {
            sent = yield* answer(match.message, {
              linkPreviewOptions: { isDisabled: true },
              text: preview,
            });
            lastLength = preview.length;
            continue;
          }
          const cutoff = streamCutoff(match.message.chat.type !== "private", preview.length);
          const now = dependencies.monotonicMilliseconds();
          if (preview.length - lastLength < cutoff || now - lastEdit < 800) continue;
          yield* editMessageText({
            chatId: sent.chat.id,
            messageId: sent.messageId,
            text: preview,
          });
          lastLength = preview.length;
          lastEdit = now;
        }
        if (sent === undefined) {
          return yield* answer(match.message, "No response received from AI. Please try again.");
        }
        yield* editRich(sent, content);
      }).pipe(Effect.ensuring(Effect.sync(() => stream.abort())));
    }),
    usage: "/ask [query]",
  };
  return definition;
}

function editCommand(ai: Ai): CommandDefinition {
  return {
    apiKey: "openrouterApiKey",
    availability: "whitelist",
    dailyLimit: 20,
    description: "Generate an image, or reply to an image to edit it.",
    example: "/edit Make it look like a painting",
    names: ["edit"],
    run: Effect.fn("editImage")(function* (match) {
      if (match.argText.length === 0) {
        return yield* answer(match.message, "Please provide a prompt describing the image.");
      }
      const replied = match.message.replyToMessage;
      const source = replied === undefined ? undefined : yield* messageImage(replied, true);
      const generated = yield* ai.image(match.argText, source).pipe(Effect.catch((error) => answer(
        match.message,
        error._tag === "AiError" && error.description === "moderation"
          ? "The generated image was rejected by content moderation. Try a different prompt or source image."
          : "AI request failed. Please try again.",
      ).pipe(Effect.as(undefined))));
      if (generated === undefined) return;
      const requester = match.message.from?.username === undefined
        ? `User ${match.message.from?.id ?? "unknown"}`
        : `@${match.message.from.username}`;
      const buffer = new ArrayBuffer(generated.byteLength);
      new Uint8Array(buffer).set(generated);
      yield* sendPhoto({
        caption: `📝 Requested by ${requester}\n🎨 Prompt: ${match.argText}`,
        chatId: match.message.chat.id,
        photo: new File([buffer], "generated.png", { type: "image/png" }),
      });
    }),
    usage: "/edit [prompt]",
  };
}

export function askCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  const ai = new Ai(dependencies);
  return [askCommand(dependencies, ai), editCommand(ai)];
}
