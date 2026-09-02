import telegramifyMarkdown from "telegramify-markdown";
import {
  Effect,
  editMessageText,
  respondTo,
  sendDocument,
  sendMessage,
  type Bot,
  type BotApiError,
  type InlineKeyboardMarkup,
  type Message,
} from "telly";

import { answer } from "./command.ts";

interface MarkdownOptions {
  readonly documentName?: string;
  readonly linkPreviewDisabled?: boolean;
  readonly replyMarkup?: InlineKeyboardMarkup;
}

function canFallback(error: BotApiError): boolean {
  return error.reason._tag === "TelegramRejected";
}

function formatted(text: string): string | undefined {
  try {
    const value = telegramifyMarkdown(text, "escape");
    return value.length <= 4_096 ? value : undefined;
  } catch {
    return undefined;
  }
}

export function editMarkdownOrPlain(
  chatId: number,
  messageId: number,
  text: string,
): Effect.Effect<Message | true, BotApiError, Bot> {
  const markdown = formatted(text);
  if (markdown === undefined) return editMessageText({ chatId, messageId, text });
  return Effect.result(editMessageText({
    chatId,
    messageId,
    parseMode: "MarkdownV2",
    text: markdown,
  })).pipe(Effect.flatMap((result) =>
    result._tag === "Success"
      ? Effect.succeed(result.success)
      : canFallback(result.failure)
      ? editMessageText({ chatId, messageId, text })
      : Effect.fail(result.failure)));
}

export function replyMarkdownOrPlain(
  message: Message,
  text: string,
  options: MarkdownOptions = {},
): Effect.Effect<Message, BotApiError, Bot> {
  const markdown = formatted(text);
  const base = {
    ...(options.linkPreviewDisabled === true
      ? { linkPreviewOptions: { isDisabled: true } }
      : {}),
    ...(options.replyMarkup === undefined ? {} : { replyMarkup: options.replyMarkup }),
  };
  const plain = text.length <= 4_096
    ? answer(message, { ...base, text })
    : sendDocument({
        ...respondTo(message),
        ...base,
        document: new File([text], options.documentName ?? "response.txt", {
          type: "text/plain",
        }),
      });
  if (markdown === undefined) return plain;
  return Effect.result(answer(message, {
    ...base,
    parseMode: "MarkdownV2",
    text: markdown,
  })).pipe(Effect.flatMap((result) =>
    result._tag === "Success"
      ? Effect.succeed(result.success)
      : canFallback(result.failure)
      ? plain
      : Effect.fail(result.failure)));
}

export function sendMarkdownOrPlain(
  chatId: number,
  text: string,
  options: MarkdownOptions = {},
): Effect.Effect<Message, BotApiError, Bot> {
  const markdown = formatted(text);
  const base = {
    chatId,
    ...(options.linkPreviewDisabled === true
      ? { linkPreviewOptions: { isDisabled: true } }
      : {}),
    ...(options.replyMarkup === undefined ? {} : { replyMarkup: options.replyMarkup }),
  };
  const plain = text.length <= 4_096
    ? sendMessage({ ...base, text })
    : sendDocument({
        ...base,
        document: new File([text], options.documentName ?? "response.txt", {
          type: "text/plain",
        }),
      });
  if (markdown === undefined) return plain;
  return Effect.result(sendMessage({
    ...base,
    parseMode: "MarkdownV2",
    text: markdown,
  })).pipe(Effect.flatMap((result) =>
    result._tag === "Success"
      ? Effect.succeed(result.success)
      : canFallback(result.failure)
      ? plain
      : Effect.fail(result.failure)));
}
