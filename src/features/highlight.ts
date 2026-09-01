import {
  answerCallback,
  callbackData,
  callbackTarget,
  editMessageReplyMarkup,
  Effect,
  getMe,
  html,
  Schema,
  sendMessage,
  type UpdateHandler,
} from "telly";

import {
  answer,
  type CommandDefinition,
} from "../app/command.ts";
import { callbackRoute, ignoreUnchangedMessage } from "../app/callback.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const HighlightCallback = callbackData("highlight", Schema.Struct({
  highlightId: Schema.Int,
  userId: Schema.Int,
}));

function highlightKeyboard(
  dependencies: AppDependencies,
  chatId: number,
  userId: number,
  botUsername?: string,
) {
  return dependencies.database.all(
    "SELECT id, string FROM highlights WHERE chat_id = ? AND user_id = ? ORDER BY id",
    [chatId, userId],
  ).pipe(Effect.map((rows) => ({
    inlineKeyboard: [
      ...rows.map((row) => [{
        ...HighlightCallback.button(`${rowString(row, "string")} 🗑`, {
          highlightId: rowNumber(row, "id"),
          userId,
        }),
        style: "danger" as const,
      }]),
      ...(botUsername === undefined
        ? []
        : [[{ style: "primary" as const, text: "Start DM", url: `https://t.me/${botUsername}` }]]),
    ],
  })));
}

function messageLink(chatId: number, username: string | undefined, messageId: number): string {
  if (username !== undefined) return `https://t.me/${username}/${messageId}`;
  const value = String(chatId);
  return value.startsWith("-100") ? `https://t.me/c/${value.slice(4)}/${messageId}` : "";
}

export function highlightFeature(dependencies: AppDependencies) {
  const definition: CommandDefinition = {
    description: "Get a direct message when text appears in this chat.",
    example: "/highlight Elden Ring",
    names: ["highlight", "hl"],
    run: Effect.fn("highlight")(function* (match) {
      const user = match.message.from;
      if (user === undefined) return;
      let botUsername: string | undefined;
      let text = "Your highlights in this chat.\n\nAdd new highlights with:\n\n<pre>/highlight [STRING]</pre>";
      if (match.argText.length > 0) {
        if (match.argText.length > 100) {
          return yield* answer(match.message, "Highlight cannot be greater than 100 characters.");
        }
        const result = yield* dependencies.database.execute(
          "INSERT OR IGNORE INTO highlights (chat_id, string, user_id) VALUES (?, ?, ?)",
          [match.message.chat.id, match.argText, user.id],
        );
        if (result.rowsAffected === 0) return yield* answer(
          match.message,
          "Highlight already exists.",
        );
        const bot = yield* getMe();
        botUsername = bot.username;
        text = `Added highlight: <code>${html.escape(match.argText)}</code>.\n\n⚠️ Message me first, otherwise I cannot send you a direct message.\n\nYour highlights in this chat:`;
      }
      return yield* answer(match.message, {
        parseMode: "HTML",
        replyMarkup: yield* highlightKeyboard(
          dependencies,
          match.message.chat.id,
          user.id,
          botUsername,
        ),
        text,
      });
    }),
    usage: "/highlight [text]",
  };
  const callback = callbackRoute("highlight", HighlightCallback, Effect.fn("highlightCallback")(function* ({
    callbackQuery,
    data,
  }) {
    if (data.userId !== callbackQuery.from.id) {
      yield* answerCallback(callbackQuery, { text: "You can only delete your own highlights." });
      return;
    }
    yield* dependencies.database.execute(
      "DELETE FROM highlights WHERE id = ? AND user_id = ?",
      [data.highlightId, data.userId],
    );
    yield* answerCallback(callbackQuery, { text: "Deleted highlight." });
    const message = callbackQuery.message;
    if (message === undefined) return;
    const target = callbackTarget(callbackQuery);
    if ("ephemeralMessageId" in target) return;
    yield* ignoreUnchangedMessage(editMessageReplyMarkup({
      ...target,
      replyMarkup: yield* highlightKeyboard(
        dependencies,
        message.chat.id,
        data.userId,
      ),
    }));
  }));
  const handler: UpdateHandler<never, void> = Effect.fn("highlightWorker")(function* (update) {
    const message = update.message;
    const sender = message?.from;
    if (
      message?.text === undefined ||
      sender === undefined ||
      message.chat.type === "private"
    ) return;
    const rows = yield* dependencies.database.all(
      "SELECT id, string, user_id FROM highlights WHERE chat_id = ? AND enabled = 1",
      [message.chat.id],
    );
    for (const row of rows) {
      const keyword = rowString(row, "string");
      if (!message.text.toLowerCase().includes(keyword.toLowerCase())) continue;
      yield* Effect.result(sendMessage({
        chatId: rowNumber(row, "user_id"),
        parseMode: "HTML",
        replyMarkup: {
          inlineKeyboard: [[{
            ...HighlightCallback.button("Delete Highlight", {
              highlightId: rowNumber(row, "id"),
              userId: rowNumber(row, "user_id"),
            }),
            style: "danger",
          }]],
        },
        text: `Your highlight <code>${html.escape(keyword)}</code> was mentioned in <b>${html.escape(message.chat.title ?? String(message.chat.id))}</b> by <a href="tg://user?id=${sender.id}">${html.escape(sender.firstName)}</a>.\n\n🔗 <a href="${messageLink(message.chat.id, message.chat.username, message.messageId)}">Link</a>`,
      }));
    }
  }, Effect.catch((error) => Effect.logError("Highlight worker failed").pipe(
    Effect.annotateLogs({ error: String(error) }),
  )));
  return { callback, commands: [definition] as const, handler };
}
