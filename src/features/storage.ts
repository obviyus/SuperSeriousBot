import {
  Effect,
  forwardMessage,
  html,
  messageMedia,
  replyTo,
  sendAnimation,
  sendAudio,
  sendDocument,
  sendPhoto,
  sendSticker,
  sendVideo,
  sendVideoNote,
  sendVoice,
  type Message,
} from "telly";

import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";

interface StoredMedia {
  readonly fileId: string;
  readonly fileUniqueId: string;
  readonly type: "ANIMATION" | "AUDIO" | "DOCUMENT" | "PHOTO" | "STICKER" | "VIDEO" | "VIDEO_NOTE" | "VOICE";
}

function storedMedia(message: Message): StoredMedia | undefined {
  const media = messageMedia(message);
  if (media === undefined || media.type === "livePhoto") return undefined;
  switch (media.type) {
    case "animation":
      return { fileId: media.animation.fileId, fileUniqueId: media.animation.fileUniqueId, type: "ANIMATION" };
    case "audio":
      return { fileId: media.audio.fileId, fileUniqueId: media.audio.fileUniqueId, type: "AUDIO" };
    case "document":
      return { fileId: media.document.fileId, fileUniqueId: media.document.fileUniqueId, type: "DOCUMENT" };
    case "photo":
      return { fileId: media.photo.fileId, fileUniqueId: media.photo.fileUniqueId, type: "PHOTO" };
    case "sticker":
      return { fileId: media.sticker.fileId, fileUniqueId: media.sticker.fileUniqueId, type: "STICKER" };
    case "video":
      return { fileId: media.video.fileId, fileUniqueId: media.video.fileUniqueId, type: "VIDEO" };
    case "videoNote":
      return { fileId: media.videoNote.fileId, fileUniqueId: media.videoNote.fileUniqueId, type: "VIDEO_NOTE" };
    case "voice":
      return { fileId: media.voice.fileId, fileUniqueId: media.voice.fileUniqueId, type: "VOICE" };
  }
}

function sendStored(target: Message, type: string, fileId: string) {
  const destination = replyTo(target);
  switch (type) {
    case "ANIMATION":
      return sendAnimation({ ...destination, animation: fileId });
    case "AUDIO":
      return sendAudio({ ...destination, audio: fileId });
    case "DOCUMENT":
      return sendDocument({ ...destination, document: fileId });
    case "PHOTO":
      return sendPhoto({ ...destination, photo: fileId });
    case "STICKER":
      return sendSticker({ ...destination, sticker: fileId });
    case "VIDEO":
      return sendVideo({ ...destination, video: fileId });
    case "VIDEO_NOTE":
      return sendVideoNote({ ...destination, videoNote: fileId });
    case "VOICE":
      return sendVoice({ ...destination, voice: fileId });
    default:
      return answer(target, "Stored object has an invalid or unsupported type.");
  }
}

function setCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Reply to media to store it under a key.",
    example: "/set rickroll",
    names: ["set"],
    run: Effect.fn("setObject")(function* (match) {
      const user = match.message.from;
      const replied = match.message.replyToMessage;
      if (user === undefined || replied === undefined) return yield* usage(match.message, definition);
      const media = storedMedia(replied);
      if (media === undefined) {
        return yield* answer(match.message, "Could not find a media object in the message.");
      }
      const key = match.args[0]?.toLowerCase();
      if (key === undefined || key.length === 0) {
        return yield* answer(replied, "Please specify a key name for the object.");
      }
      const result = yield* dependencies.database.execute(
        `INSERT OR IGNORE INTO object_store (key, file_id, file_unique_id, user_id, type)
         VALUES (?, ?, ?, ?, ?)`,
        [key, media.fileId, media.fileUniqueId, user.id, media.type],
      );
      if (result.rowsAffected === 0) {
        const existing = yield* dependencies.database.one(
          "SELECT key FROM object_store WHERE file_unique_id = ?",
          [media.fileUniqueId],
        );
        return yield* answer(match.message, {
          parseMode: "HTML",
          text: existing === undefined
            ? `Object with key <code>${html.escape(key)}</code> already exists.`
            : `This file has already been stored with key <code>${html.escape(rowString(existing, "key"))}</code>.`,
        });
      }
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `Object with key <code>${html.escape(key)}</code> saved. Use <code>/get ${html.escape(key)}</code> to retrieve it.`,
      });
    }),
    usage: "/set [key]",
  };
  return definition;
}

function getCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Get a stored media object.",
    example: "/get rickroll",
    names: ["get"],
    run: Effect.fn("getObject")(function* (match) {
      const key = match.args[0]?.toLowerCase();
      if (key === undefined || key.length === 0) return yield* usage(match.message, definition);
      const row = yield* dependencies.database.one(
        "SELECT id, file_id, type FROM object_store WHERE key = ? COLLATE NOCASE",
        [key],
      );
      if (row === undefined) return yield* answer(match.message, {
        parseMode: "HTML",
        text: `Object with key <code>${html.escape(key)}</code> does not exist.`,
      });
      yield* sendStored(
        match.message.replyToMessage ?? match.message,
        rowString(row, "type"),
        rowString(row, "file_id"),
      );
      yield* dependencies.database.execute(
        "UPDATE object_store SET fetch_count = fetch_count + 1 WHERE id = ?",
        [rowNumber(row, "id")],
      );
    }),
    usage: "/get [key]",
  };
  return definition;
}

function addQuoteCommand(dependencies: AppDependencies): CommandDefinition {
  const definition: CommandDefinition = {
    description: "Reply to a message to save it into QuotesDB.",
    example: "/addquote",
    names: ["addquote"],
    run: Effect.fn("addQuote")(function* (match) {
      const saver = match.message.from;
      const quoted = match.message.replyToMessage;
      if (saver === undefined || quoted?.from === undefined) {
        return yield* usage(match.message, definition);
      }
      if (quoted.hasProtectedContent === true) {
        return yield* answer(match.message, "This is protected and cannot be forwarded.");
      }
      const existing = yield* dependencies.database.one(
        "SELECT 1 FROM quote_db WHERE chat_id = ? AND message_id = ?",
        [quoted.chat.id, quoted.messageId],
      );
      if (existing !== undefined) {
        return yield* answer(match.message, "This message has already been saved.");
      }
      const forwarded = yield* forwardMessage({
        chatId: dependencies.config.quoteChannelId,
        fromChatId: quoted.chat.id,
        messageId: quoted.messageId,
      });
      yield* dependencies.database.execute(
        `INSERT INTO quote_db (
          message_id, chat_id, message_user_id, saver_user_id, forwarded_message_id
        ) VALUES (?, ?, ?, ?, ?)`,
        [quoted.messageId, quoted.chat.id, quoted.from.id, saver.id, forwarded.messageId],
      );
      return yield* answer(
        match.message,
        `Quote added by @${saver.username ?? saver.firstName}.`,
      );
    }),
    usage: "/addquote",
  };
  return definition;
}

function randomQuote(dependencies: AppDependencies, chatId: number, authorId?: number) {
  return dependencies.database.one(
    `SELECT * FROM quote_db
     WHERE chat_id = ?
     ${authorId === undefined ? "" : "AND message_user_id = ?"}
     AND id NOT IN (SELECT quote_id FROM quote_recent_history WHERE chat_id = ?)
     ORDER BY RANDOM() LIMIT 1`,
    authorId === undefined ? [chatId, chatId] : [chatId, authorId, chatId],
  );
}

function quoteCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Return a random saved message from this group.",
    example: "/quote @obviyus",
    names: ["quote", "q"],
    run: Effect.fn("quote")(function* (match) {
      const username = match.args[0]?.replace(/^@/u, "").toLowerCase();
      const author = username === undefined
        ? undefined
        : yield* dependencies.database.one(
            "SELECT user_id FROM user_stats WHERE LOWER(username) = ?",
            [username],
          );
      if (username !== undefined && author === undefined) {
        return yield* answer(match.message, `@${username} not found.`);
      }
      const authorId = author === undefined ? undefined : rowNumber(author, "user_id");
      let row = yield* randomQuote(dependencies, match.message.chat.id, authorId);
      if (row === undefined) {
        yield* dependencies.database.execute(
          authorId === undefined
            ? "DELETE FROM quote_recent_history WHERE chat_id = ?"
            : `DELETE FROM quote_recent_history WHERE chat_id = ? AND quote_id IN (
                SELECT id FROM quote_db WHERE message_user_id = ?
              )`,
          authorId === undefined
            ? [match.message.chat.id]
            : [match.message.chat.id, authorId],
        );
        row = yield* randomQuote(dependencies, match.message.chat.id, authorId);
      }
      if (row === undefined) {
        return yield* answer(
          match.message,
          username === undefined
            ? "No quotes found in this chat."
            : `No quotes found by @${username}.`,
        );
      }
      yield* dependencies.database.execute(
        "INSERT INTO quote_recent_history (chat_id, quote_id) VALUES (?, ?)",
        [match.message.chat.id, rowNumber(row, "id")],
      );
      const forwardedMessageId = row["forwarded_message_id"];
      if (typeof forwardedMessageId !== "number") {
        yield* dependencies.database.batch([
          { sql: "DELETE FROM quote_recent_history WHERE quote_id = ?", args: [rowNumber(row, "id")] },
          { sql: "DELETE FROM quote_db WHERE id = ?", args: [rowNumber(row, "id")] },
        ]);
        return yield* answer(match.message, "Quoted message deleted. Removing the quote.");
      }
      const delivery = yield* Effect.result(forwardMessage({
        chatId: match.message.chat.id,
        fromChatId: dependencies.config.quoteChannelId,
        messageId: forwardedMessageId,
      }));
      if (delivery._tag === "Success") return;
      yield* dependencies.database.batch([
        { sql: "DELETE FROM quote_recent_history WHERE quote_id = ?", args: [rowNumber(row, "id")] },
        { sql: "DELETE FROM quote_db WHERE id = ?", args: [rowNumber(row, "id")] },
      ]);
      yield* answer(match.message, "Quoted message deleted. Removing the quote.");
    }),
    usage: "/quote [optional username]",
  };
}

export function storageCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  return [
    setCommand(dependencies),
    getCommand(dependencies),
    addQuoteCommand(dependencies),
    quoteCommand(dependencies),
  ];
}
