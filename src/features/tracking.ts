import {
  Effect,
  messageEntities,
  type Update,
  type UpdateHandler,
} from "telly";

import { rowNumber } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

function link(chatId: number, username: string | undefined, messageId: number): string | null {
  if (username !== undefined) return `https://t.me/${username}/${messageId}`;
  const id = String(chatId);
  return id.startsWith("-100") ? `https://t.me/c/${id.slice(4)}/${messageId}` : null;
}

function userIdForMention(dependencies: AppDependencies, username: string) {
  return dependencies.database.one(
    "SELECT user_id FROM user_stats WHERE LOWER(username) = ?",
    [username.replace(/^@/u, "").toLowerCase()],
  ).pipe(Effect.map((row) => row === undefined ? undefined : rowNumber(row, "user_id")));
}

function saveMention(
  dependencies: AppDependencies,
  chatId: number,
  messageId: number,
  fromUserId: number,
  mentionedUserId: number,
) {
  return dependencies.database.execute(
    `INSERT INTO chat_mentions (
      mentioning_user_id, mentioned_user_id, chat_id, message_id
    ) VALUES (?, ?, ?, ?)`,
    [fromUserId, mentionedUserId, chatId, messageId],
  );
}

export function trackingHandler(dependencies: AppDependencies): UpdateHandler<never, void> {
  return Effect.fn("tracking")(function* (update: Update) {
    const message = update.message;
    const user = message?.from;
    if (message === undefined || user === undefined) return;
    const mentioned = new Set<number>();
    for (const span of messageEntities(message, "mention", "text_mention")) {
      const userId = span.entity.user?.id ?? (span.entity.type === "mention"
        ? yield* userIdForMention(dependencies, span.text)
        : undefined);
      if (userId === undefined || mentioned.has(userId)) continue;
      mentioned.add(userId);
      yield* saveMention(
        dependencies,
        message.chat.id,
        message.messageId,
        user.id,
        userId,
      );
    }
    const repliedUserId = message.replyToMessage?.from?.id;
    if (repliedUserId !== undefined && !mentioned.has(repliedUserId)) {
      yield* saveMention(
        dependencies,
        message.chat.id,
        message.messageId,
        user.id,
        repliedUserId,
      );
    }
    if (message.text === undefined || message.text.startsWith("/")) return;
    if (user.username !== undefined) {
      yield* dependencies.database.execute(
        `INSERT INTO user_stats (user_id, username, first_name, last_seen, last_message_link)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(user_id) DO UPDATE SET
           username = excluded.username,
           first_name = excluded.first_name,
           last_seen = excluded.last_seen,
           last_message_link = excluded.last_message_link`,
        [
          user.id,
          user.username,
          user.firstName,
          dependencies.now().toISOString(),
          link(message.chat.id, message.chat.username, message.messageId),
        ],
      );
    }
    const setting = yield* dependencies.database.one(
      "SELECT fts FROM group_settings WHERE chat_id = ?",
      [message.chat.id],
    );
    yield* dependencies.database.execute(
      `INSERT OR IGNORE INTO chat_stats (
        chat_id, user_id, message_id, message_text,
        reply_to_message_id, reply_to_user_id
      ) VALUES (?, ?, ?, ?, ?, ?)`,
      [
        message.chat.id,
        user.id,
        message.messageId,
        setting?.["fts"] === 1 ? message.text : null,
        message.replyToMessage?.messageId ?? null,
        repliedUserId ?? null,
      ],
    );
  }, Effect.catch((error) => Effect.logError("Message tracking failed").pipe(
    Effect.annotateLogs({ error: String(error) }),
  )));
}
