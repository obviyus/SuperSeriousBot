import {
  deleteMessage,
  editMessageText,
  Effect,
  replyTo,
  respondTo,
  sendDocument,
  sendMessage,
  sendRichMessage,
  type BotApiError,
  type ConversationMessage,
  type ConversationTarget,
  type InputRichBlock,
  type InlineKeyboardMarkup,
  type Message,
  type ReplyTarget,
  type RichText,
} from "telly";

const plainMessageLimit = 4_096;
export const richMessageLimit = 32_768;

export const richMarkdownPrompt = `Format the user-visible answer as Telegram Rich Markdown.
Use GitHub-flavored Markdown headings, lists, task lists, blockquotes, fenced code, tables, links, dividers, footnotes, and math when useful. Use ==text== for highlighting and ||text|| for spoilers.
Write prices with ISO currency codes such as USD 48,500, never with dollar symbols. Use $...$ only for intentional mathematical expressions.
Return only the answer without an outer code fence. Do not emit HTML, media, or buttons. Keep the answer under 32,768 characters.`;

interface RichOptions {
  readonly documentName?: string;
  readonly replyMarkup?: InlineKeyboardMarkup;
}

type RichTarget = ConversationTarget | ReplyTarget;

export const rich = {
  bold: (text: RichText): RichText => ({ text, type: "bold" }),
  code: (text: RichText): RichText => ({ text, type: "code" }),
  command: (command: string): RichText => ({
    botCommand: command,
    text: command,
    type: "bot_command",
  }),
  dateTime: (unixTime: number, dateTimeFormat: string, text: RichText): RichText => ({
    dateTimeFormat,
    text,
    type: "date_time",
    unixTime,
  }),
  footer: (text: RichText): InputRichBlock => ({ text, type: "footer" }),
  heading: (text: RichText, size = 2): InputRichBlock => ({ size, text, type: "heading" }),
  link: (text: RichText, url: string): RichText => ({ text, type: "url", url }),
  list: (
    items: ReadonlyArray<RichText>,
    options: { readonly ordered?: boolean } = {},
  ): InputRichBlock => ({
    items: items.map((text, index) => ({
      blocks: [{ text, type: "paragraph" }],
      ...(options.ordered === true ? { type: "1", value: index + 1 } : {}),
    })),
    type: "list",
  }),
  paragraph: (text: RichText): InputRichBlock => ({ text, type: "paragraph" }),
  pre: (text: RichText): InputRichBlock => ({ text, type: "pre" }),
  table: (
    rows: ReadonlyArray<ReadonlyArray<RichText>>,
    options: { readonly header?: boolean } = {},
  ): InputRichBlock => ({
    cells: rows.map((row, rowIndex) => row.map((text) => ({
      align: "left",
      text,
      valign: "middle",
      ...(options.header === true && rowIndex === 0 ? { isHeader: true as const } : {}),
    }))),
    type: "table",
  }),
} as const;

function conversationTarget(message: ConversationMessage): RichTarget {
  return message.chat.type === "private" ? respondTo(message) : replyTo(message);
}

function plain(target: RichTarget, text: string, options: RichOptions) {
  const replyMarkup = {
    ...(options.replyMarkup === undefined ? {} : { replyMarkup: options.replyMarkup }),
  };
  return text.length <= plainMessageLimit
    ? sendMessage({
        ...target,
        ...replyMarkup,
        linkPreviewOptions: { isDisabled: true },
        text,
      })
    : sendDocument({
        ...target,
        ...replyMarkup,
        document: new File([text], options.documentName ?? "response.txt", {
          type: "text/plain",
        }),
      });
}

function sendAt(target: RichTarget, text: string, options: RichOptions) {
  const fallback = plain(target, text, options);
  if (text.length > richMessageLimit) return fallback;
  return Effect.result(sendRichMessage({
    ...target,
    ...(options.replyMarkup === undefined ? {} : { replyMarkup: options.replyMarkup }),
    richMessage: { markdown: text },
  })).pipe(Effect.flatMap((result) =>
    result._tag === "Success"
      ? Effect.succeed(result.success)
      : result.failure.reason._tag === "TelegramRejected"
      ? fallback
      : Effect.fail(result.failure)));
}

export const replyRich = Effect.fn("replyRich")(function* (
  message: ConversationMessage,
  text: string,
  options: RichOptions = {},
) {
  return yield* sendAt(conversationTarget(message), text, options);
});

export const replyBlocks = Effect.fn("replyBlocks")(function* (
  message: ConversationMessage,
  blocks: ReadonlyArray<InputRichBlock>,
  options: Pick<RichOptions, "replyMarkup"> = {},
) {
  return yield* sendRichMessage({
    ...conversationTarget(message),
    ...(options.replyMarkup === undefined ? {} : { replyMarkup: options.replyMarkup }),
    richMessage: { blocks },
  });
});

export const sendRich = Effect.fn("sendRich")(function* (
  chatId: number,
  text: string,
  options: RichOptions = {},
) {
  return yield* sendAt({ chatId }, text, options);
});

function notModified(error: BotApiError): boolean {
  return error.reason._tag === "TelegramRejected" &&
    error.reason.description.toLowerCase().includes("message is not modified");
}

export const editRich = Effect.fn("editRich")(function* (message: Message, text: string) {
  if (text.length <= richMessageLimit) {
    const edited = yield* Effect.result(editMessageText({
      chatId: message.chat.id,
      messageId: message.messageId,
      richMessage: { markdown: text },
    }));
    if (edited._tag === "Success" || notModified(edited.failure)) return;
    if (edited.failure.reason._tag !== "TelegramRejected") {
      return yield* Effect.fail(edited.failure);
    }
    if (text.length <= plainMessageLimit) {
      yield* editMessageText({
        chatId: message.chat.id,
        messageId: message.messageId,
        text,
      });
      return;
    }
  }
  yield* plain(respondTo(message), text, {});
  yield* deleteMessage({
    chatId: message.chat.id,
    messageId: message.messageId,
  }).pipe(Effect.catch(() => Effect.void));
});
