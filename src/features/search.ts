import { chunksOf, lastNonEmpty } from "effect/Array";
import {
  deleteMessage,
  downloadFile,
  editMessageText,
  Effect,
  getChatAdministrators,
  messageText,
  Schema,
} from "telly";

import { Ai } from "../app/ai.ts";
import { isAdmin } from "../app/admin.ts";
import {
  answer,
  type CommandDefinition,
} from "../app/command.ts";
import { rowNumber, rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { replyRich } from "../app/rich.ts";
import { getModel, normalizeModelName } from "./settings.ts";
import { answerSearch, excludedUserIds } from "./search-agent.ts";
import { refreshSearchMembership, searchStorePath, syncSearchStores } from "./search-store.ts";

const embeddingModel = "qwen/qwen3-embedding-8b";
const Persona = Schema.Struct({
  aliases: Schema.Array(Schema.Struct({ alias: Schema.String, confidence: Schema.Number })),
  sheet: Schema.String,
});
const Lore = Schema.Struct({
  items: Schema.Array(Schema.Struct({
    receipts: Schema.Array(Schema.Int),
    summary: Schema.String,
    topic: Schema.String,
  })),
});
const ExportPart = Schema.Union([
  Schema.String,
  Schema.Struct({ text: Schema.String, type: Schema.optionalKey(Schema.String) }),
]);
const TelegramExport = Schema.Struct({
  messages: Schema.Array(Schema.Struct({
    date: Schema.String,
    from_id: Schema.optionalKey(Schema.String),
    id: Schema.Int,
    reply_to_message_id: Schema.optionalKey(Schema.Int),
    text: Schema.Union([Schema.String, Schema.Array(ExportPart)]),
    type: Schema.String,
  })),
});

export interface SourceMessage {
  readonly author: string;
  readonly createTime: string;
  readonly messageId: number;
  readonly text: string;
  readonly userId: number;
}

export interface SearchWindow {
  readonly endMessageId: number;
  readonly endTime: string;
  readonly messageCount: number;
  readonly startMessageId: number;
  readonly startTime: string;
  readonly text: string;
}

export function buildWindows(messages: ReadonlyArray<SourceMessage>): ReadonlyArray<SearchWindow> {
  const windows: Array<SearchWindow> = [];
  for (let start = 0; start < messages.length; start += 8) {
    const chunk = messages.slice(start, start + 24);
    const first = chunk[0];
    const last = chunk.at(-1);
    if (first === undefined || last === undefined) continue;
    windows.push({
      endMessageId: last.messageId,
      endTime: last.createTime,
      messageCount: chunk.length,
      startMessageId: first.messageId,
      startTime: first.createTime,
      text: chunk.map((message) =>
        `${message.messageId} ${message.createTime} ${message.author}: ${message.text}`
      ).join("\n"),
    });
  }
  return windows;
}

export function buildUtterances(messages: ReadonlyArray<SourceMessage>): ReadonlyArray<SearchWindow & { readonly userId: number; readonly author: string }> {
  const groups: Array<[SourceMessage, ...Array<SourceMessage>]> = [];
  for (const message of messages) {
    const current = groups.at(-1);
    if (current === undefined || current[0].userId !== message.userId || current.length === 12 ||
      new Date(message.createTime).getTime() - new Date(lastNonEmpty(current).createTime).getTime() > 300_000) {
      groups.push([message]);
    } else current.push(message);
  }
  return groups.map((group) => {
    const first = group[0];
    const last = lastNonEmpty(group);
    return {
      author: first.author,
      endMessageId: last.messageId,
      endTime: last.createTime,
      messageCount: group.length,
      startMessageId: first.messageId,
      startTime: first.createTime,
      text: group.map((message) => `${message.messageId} ${message.text}`).join("\n"),
      userId: first.userId,
    };
  });
}

const SourceTail = Schema.Array(Schema.Struct({
  author: Schema.String,
  createTime: Schema.String,
  messageId: Schema.Int,
  text: Schema.String,
  userId: Schema.Int,
}));

function sourceMessages(dependencies: AppDependencies, chatId: number, through: number | null, after?: number) {
  return dependencies.database.all(
    `SELECT messages.message_id, messages.user_id, messages.create_time,
            COALESCE(users.username, 'user:' || messages.user_id) AS author,
            messages.message_text
     FROM chat_stats messages
     LEFT JOIN user_stats users ON users.user_id = messages.user_id
     WHERE messages.chat_id = ? AND messages.message_id IS NOT NULL
       AND messages.message_text IS NOT NULL AND messages.message_text != ''
       AND messages.message_text NOT LIKE '/%'
       AND messages.message_id <= ?
       ${after === undefined ? "" : "AND messages.message_id > ?"}
     ORDER BY messages.message_id`,
    after === undefined ? [chatId, through] : [chatId, through, after],
  ).pipe(Effect.map((rows): ReadonlyArray<SourceMessage> => rows.map((row) => ({
    author: rowString(row, "author").startsWith("user:")
      ? rowString(row, "author")
      : `@${rowString(row, "author")}`,
    createTime: rowString(row, "create_time"),
    messageId: rowNumber(row, "message_id"),
    text: rowString(row, "message_text"),
    userId: rowNumber(row, "user_id"),
  }))));
}

function indexChat(dependencies: AppDependencies, ai: Ai, chatId: number) {
  return Effect.gen(function* () {
    const profile = [chatId, embeddingModel];
    const profileWhere = `chat_id = ? AND embedding_model = ?
      AND window_dimension = 1024 AND utterance_dimension = 256`;
    yield* dependencies.database.execute(
      `INSERT INTO chat_search_progress (chat_id, embedding_model, window_dimension, utterance_dimension)
       VALUES (?, ?, 1024, 256) ON CONFLICT DO NOTHING`,
      profile,
    );
    const progress = yield* dependencies.database.one(
      `UPDATE chat_search_progress SET generation = generation + 1
       WHERE ${profileWhere} AND revision != indexed_revision
       RETURNING revision, generation, rebuild, end_message_id, window_tail, utterance_tail,
         (SELECT MAX(message_id) FROM chat_stats WHERE chat_id = chat_search_progress.chat_id) AS source_end_message_id`,
      profile,
    );
    if (progress === undefined) return;
    const revision = rowNumber(progress, "revision");
    const through = progress["source_end_message_id"] === null ? null : rowNumber(progress, "source_end_message_id");
    const generation = rowNumber(progress, "generation");
    const rebuild = rowNumber(progress, "rebuild") === 1;
    const after = rebuild || progress["end_message_id"] === null
      ? undefined : rowNumber(progress, "end_message_id");
    const messages = yield* sourceMessages(dependencies, chatId, through, after);
    const windowMessages = [
      ...(rebuild ? [] : Schema.decodeUnknownSync(SourceTail)(JSON.parse(rowString(progress, "window_tail")))),
      ...messages,
    ];
    const utteranceMessages = [
      ...(rebuild ? [] : Schema.decodeUnknownSync(SourceTail)(JSON.parse(rowString(progress, "utterance_tail")))),
      ...messages,
    ];
    const windows = buildWindows(windowMessages);
    const utterances = buildUtterances(utteranceMessages);
    const guard = `EXISTS (SELECT 1 FROM chat_search_progress WHERE ${profileWhere}
      AND generation = ?)`;
    const guardArgs = [...profile, generation];
    const indexedWindows = new Set((windows.length === 0 ? [] : yield* dependencies.database.all(
      `SELECT start_message_id, end_message_id FROM chat_search_windows
       WHERE chat_id = ? AND embedding_model = ? AND embedding_dimension = 1024
         AND start_message_id >= ?`,
      [...profile, windows[0]!.startMessageId],
    )).map((row) => `${rowNumber(row, "start_message_id")}:${rowNumber(row, "end_message_id")}`));
    const indexedUtterances = new Set((utterances.length === 0 ? [] : yield* dependencies.database.all(
      `SELECT start_message_id, end_message_id FROM chat_search_utterances
       WHERE chat_id = ? AND embedding_model = ? AND embedding_dimension = 256
         AND start_message_id >= ?`,
      [...profile, utterances[0]!.startMessageId],
    )).map((row) => `${rowNumber(row, "start_message_id")}:${rowNumber(row, "end_message_id")}`));
    for (const batch of chunksOf(windows, 64)) {
      const missing = batch.filter((window) => !indexedWindows.has(`${window.startMessageId}:${window.endMessageId}`));
      if (missing.length === 0) continue;
      const embeddings = yield* ai.embeddings(missing.map((window) => window.text), 1_024);
      for (const [index, window] of missing.entries()) {
        const inserted = yield* dependencies.database.execute(
          `INSERT OR REPLACE INTO chat_search_windows (
            chat_id, start_message_id, end_message_id, start_time, end_time,
            message_count, message_text, embedding, embedding_model, embedding_dimension
          ) SELECT ?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 1024 WHERE ${guard}`,
          [
            chatId,
            window.startMessageId,
            window.endMessageId,
            window.startTime,
            window.endTime,
            window.messageCount,
            window.text,
            JSON.stringify(embeddings[index]!),
            embeddingModel,
            ...guardArgs,
          ],
        );
        if (inserted.rowsAffected === 0) return;
        yield* dependencies.database.execute(
          `DELETE FROM chat_search_windows
           WHERE chat_id = ? AND start_message_id = ? AND end_message_id < ?
             AND embedding_model = ? AND embedding_dimension = 1024 AND ${guard}`,
          [chatId, window.startMessageId, window.endMessageId, embeddingModel, ...guardArgs],
        );
      }
    }
    for (const batch of chunksOf(utterances, 64)) {
      const missing = batch.filter((utterance) => !indexedUtterances.has(`${utterance.startMessageId}:${utterance.endMessageId}`));
      if (missing.length === 0) continue;
      const embeddings = yield* ai.embeddings(missing.map((item) => item.text), 256);
      for (const [index, item] of missing.entries()) {
        const inserted = yield* dependencies.database.execute(
          `INSERT OR REPLACE INTO chat_search_utterances (
            chat_id, start_message_id, end_message_id, user_id, author, start_time,
            end_time, message_count, message_text, embedding, embedding_model, embedding_dimension
          ) SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 256 WHERE ${guard}`,
          [
            chatId,
            item.startMessageId,
            item.endMessageId,
            item.userId,
            item.author,
            item.startTime,
            item.endTime,
            item.messageCount,
            item.text,
            JSON.stringify(embeddings[index]!),
            embeddingModel,
            ...guardArgs,
          ],
        );
        if (inserted.rowsAffected === 0) return;
      }
    }
    // Preserve the exact overlap alignment and the final speaker group for the next append.
    const completedWindows = windows.filter((window) => window.messageCount === 24).length;
    const finalUtterance = utterances.at(-1);
    yield* dependencies.database.execute(
      `UPDATE chat_search_progress SET indexed_revision = ?, rebuild = 0,
         end_message_id = ?, window_tail = ?, utterance_tail = ?
       WHERE ${profileWhere} AND generation = ?`,
      [
        revision,
        through,
        JSON.stringify(windowMessages.slice(completedWindows * 8)),
        JSON.stringify(finalUtterance === undefined ? [] : utteranceMessages.slice(-finalUtterance.messageCount)),
        ...guardArgs,
      ],
    );
  });
}

function canModerate(dependencies: AppDependencies, chatId: number, userId: number, privateChat: boolean) {
  if (privateChat || isAdmin(dependencies, userId)) return Effect.succeed(true);
  return getChatAdministrators({ chatId }).pipe(
    Effect.map((members) => members.some((member) => member.user.id === userId)),
  );
}

function searchCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    apiKey: "openrouterApiKey",
    availability: "whitelist",
    dailyLimit: 30,
    description: "Answer from this chat's message history.",
    example: "/search what job does Nathu do",
    names: ["search"],
    run: Effect.fn("search")(function* (match) {
      if (match.argText.length === 0) return yield* answer(
        match.message,
        "Ask a question after /search. Reply to someone to search only their messages.",
      );
      const setting = yield* dependencies.database.one(
        "SELECT fts FROM group_settings WHERE chat_id = ?",
        [match.message.chat.id],
      );
      if (setting?.["fts"] !== 1) return yield* answer(
        match.message,
        "Chat search isn't enabled here. An admin can run /enable_fts.",
      );
      const status = yield* answer(match.message, "Searching messages...");
      const start = dependencies.monotonicMilliseconds();
      const replied = match.message.replyToMessage;
      const chatId = match.message.chat.id;
      const repliedText = replied === undefined ? undefined : messageText(replied);
      const result = yield* syncSearchStores(dependencies, [chatId]).pipe(
        Effect.andThen(answerSearch(
          dependencies,
          match.argText,
          chatId,
          searchStorePath(dependencies.config.stateDirectory, chatId),
          {
            ...(replied?.from === undefined ? {} : { authorId: replied.from.id }),
            ...(repliedText === undefined ? {} : { repliedText }),
          },
        )),
      ).pipe(
        Effect.ensuring(deleteMessage({
          chatId: status.chat.id,
          messageId: status.messageId,
        }).pipe(Effect.catch(() => Effect.void))),
      );
      const model = normalizeModelName(yield* getModel(dependencies, "search"));
      yield* dependencies.database.execute(
        `INSERT INTO search_events (
          chat_id, user_id, message_id, question, answer, model,
          citation_message_ids, duration_ms, lane
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'agent')`,
        [
          match.message.chat.id,
          match.message.from?.id ?? 0,
          match.message.messageId,
          match.argText,
          result.answer,
          model,
          JSON.stringify(result.citations),
          Math.round(dependencies.monotonicMilliseconds() - start),
        ],
      );
      yield* replyRich(match.message, result.answer);
    }),
    usage: "/search [question]",
  };
}

function enableCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Enable full-text search in the current chat.",
    example: "/enable_fts",
    names: ["enable_fts"],
    run: Effect.fn("enableSearch")(function* (match) {
      const user = match.message.from;
      if (user === undefined || !(yield* canModerate(
        dependencies,
        match.message.chat.id,
        user.id,
        match.message.chat.type === "private",
      ))) return yield* answer(match.message, "You are not a moderator.");
      yield* dependencies.database.execute(
        `INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
         ON CONFLICT(chat_id) DO UPDATE SET fts = 1`,
        [match.message.chat.id],
      );
      yield* answer(match.message, "Full text search has been enabled in this chat.");
    }),
    usage: "/enable_fts",
  };
}

function importCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Import a Telegram JSON export into chat search.",
    example: "/import as a reply to result.json",
    names: ["import"],
    run: Effect.fn("importSearch")(function* (match) {
      const user = match.message.from;
      if (user === undefined || !(yield* canModerate(
        dependencies,
        match.message.chat.id,
        user.id,
        match.message.chat.type === "private",
      ))) return yield* answer(match.message, "You are not a moderator.");
      const document = match.message.replyToMessage?.document;
      if (document === undefined) return yield* answer(match.message, "Please reply to a JSON file.");
      if (document.mimeType !== "application/json") return yield* answer(
        match.message,
        "Please provide a JSON file.",
      );
      const status = yield* answer(match.message, "Downloading file...");
      const bytes = yield* downloadFile({ fileId: document.fileId });
      yield* editMessageText({ chatId: status.chat.id, messageId: status.messageId, text: "Parsing JSON export..." });
      const parsed = Schema.decodeUnknownSync(TelegramExport)(JSON.parse(new TextDecoder().decode(bytes)));
      const rows = parsed.messages.flatMap((message) => {
        if (message.type !== "message" || message.from_id === undefined) return [];
        const text = typeof message.text === "string"
          ? message.text
          : message.text.map((part) => typeof part === "string" ? part : part.text).join("");
        const userId = Number(message.from_id.replace(/^user/u, ""));
        return text.length === 0 || !Number.isSafeInteger(userId) ? [] : [{ message, text, userId }];
      });
      yield* editMessageText({
        chatId: status.chat.id,
        messageId: status.messageId,
        text: `Importing ${rows.length.toLocaleString()} messages...`,
      });
      for (const batch of chunksOf(rows, 200)) {
        yield* dependencies.database.batch(batch.map(({ message, text, userId }) => ({
          args: [
            match.message.chat.id,
            userId,
            message.id,
            new Date(message.date).toISOString(),
            text,
            message.reply_to_message_id ?? null,
          ],
          sql: `INSERT INTO chat_stats (
            chat_id, user_id, message_id, create_time, message_text, reply_to_message_id
          ) VALUES (?, ?, ?, ?, ?, ?)
          ON CONFLICT(chat_id, user_id, message_id) DO NOTHING`,
        })));
      }
      yield* dependencies.database.execute(
        `INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
         ON CONFLICT(chat_id) DO UPDATE SET fts = 1`,
        [match.message.chat.id],
      );
      yield* editMessageText({
        chatId: status.chat.id,
        messageId: status.messageId,
        text: `Import complete! ${rows.length.toLocaleString()} messages imported.`,
      });
    }),
    usage: "/import as a reply to a Telegram JSON export",
  };
}

function buildMemory(dependencies: AppDependencies, ai: Ai, chatId: number) {
  return Effect.gen(function* () {
    const excluded = yield* excludedUserIds(dependencies);
    const members = (yield* dependencies.database.all(
      `SELECT utterances.user_id, COALESCE(users.username, 'user:' || utterances.user_id) AS username,
              COUNT(*) AS count, MAX(utterances.end_message_id) AS end_message_id
       FROM chat_search_utterances utterances
       LEFT JOIN user_stats users ON users.user_id = utterances.user_id
       WHERE utterances.chat_id = ?
       GROUP BY utterances.user_id HAVING count >= 200`,
      [chatId],
    )).filter((row) => !excluded.has(rowNumber(row, "user_id")));
    // The daily job only pays to summarise members and lore with new messages.
    const summarised = new Map((yield* dependencies.database.all(
      "SELECT user_id, source_end_message_id FROM chat_personas WHERE chat_id = ?",
      [chatId],
    )).map((row) => [rowNumber(row, "user_id"), rowNumber(row, "source_end_message_id")]));
    for (const member of members) {
      const userId = rowNumber(member, "user_id");
      if ((summarised.get(userId) ?? -1) >= rowNumber(member, "end_message_id")) continue;
      const utterances = yield* dependencies.database.all(
        `SELECT end_message_id, end_time, author, message_text
         FROM chat_search_utterances WHERE chat_id = ? AND user_id = ?
         ORDER BY end_message_id DESC LIMIT 400`,
        [chatId, userId],
      );
      const context = [...utterances].reverse().map((row) =>
        `${rowNumber(row, "end_message_id")} ${rowString(row, "end_time")} ${rowString(row, "author")}: ${rowString(row, "message_text").replaceAll("\n", " / ")}`
      ).join("\n");
      const persona = yield* ai.object("search", [
        {
          content: "Write a concise friend-group persona dossier using only the supplied messages. Include concrete traits and short verbatim receipts. Also return aliases used for this member with confidence from 0 to 1.",
          role: "system",
        },
        { content: context, role: "user" },
      ], Persona, { maxTokens: 2_000 });
      const allowedReceipts = new Set(context.match(/^-?\d+/gmu)?.map(Number) ?? []);
      const receipts: Array<number> = [];
      const sheet = persona.sheet.replace(
        /\[(?:msg:\s*-?\d+)(?:,\s*msg:\s*-?\d+)*\]/gu,
        (match) => {
          const valid = (match.match(/-?\d+/gu) ?? []).map(Number).filter((id) =>
            allowedReceipts.has(id));
          receipts.push(...valid);
          return valid.length === 0 ? "" : `[${valid.map((id) => `msg:${id}`).join(", ")}]`;
        },
      );
      yield* dependencies.database.execute(
        `INSERT INTO chat_personas (
          chat_id, user_id, sheet, receipts, source_end_message_id, update_time
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET
          sheet = excluded.sheet, receipts = excluded.receipts,
          source_end_message_id = excluded.source_end_message_id,
          update_time = CURRENT_TIMESTAMP`,
        [chatId, userId, sheet, JSON.stringify([...new Set(receipts)]), rowNumber(member, "end_message_id")],
      );
      for (const alias of persona.aliases.filter((item) => item.confidence >= 0.5)) {
        const normalized = alias.alias.toLowerCase().trim().replace(/\s+/gu, " ");
        if (normalized.length === 0 || ["bhai", "bro", "boss", "dude", "yaar"].includes(normalized)) continue;
        yield* dependencies.database.execute(
          `INSERT INTO chat_aliases (chat_id, user_id, alias, confidence, update_time)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(chat_id, alias) DO UPDATE SET
             user_id = CASE WHEN excluded.confidence > confidence THEN excluded.user_id ELSE user_id END,
             confidence = MAX(confidence, excluded.confidence), update_time = CURRENT_TIMESTAMP`,
          [chatId, userId, normalized, alias.confidence],
        );
      }
    }
    const windows = yield* dependencies.database.all(
      `SELECT start_message_id, end_message_id FROM chat_search_windows
       WHERE chat_id = ? ORDER BY end_message_id DESC LIMIT 100`,
      [chatId],
    );
    if (windows.length === 0) return;
    const loreEnd = yield* dependencies.database.one(
      "SELECT MAX(source_end_message_id) AS end_message_id FROM chat_lore WHERE chat_id = ?",
      [chatId],
    );
    if (loreEnd !== undefined && loreEnd["end_message_id"] !== null &&
      rowNumber(loreEnd, "end_message_id") >= rowNumber(windows[0]!, "end_message_id")) return;
    // Window text mixes speakers, so rebuild the lore source without excluded members.
    const messages = (yield* sourceMessages(
      dependencies,
      chatId,
      rowNumber(windows[0]!, "end_message_id"),
      Math.min(...windows.map((row) => rowNumber(row, "start_message_id"))) - 1,
    )).filter((message) => !excluded.has(message.userId));
    if (messages.length === 0) return;
    const storedLore = new Map((yield* dependencies.database.all(
      "SELECT topic, receipts FROM chat_lore WHERE chat_id = ?",
      [chatId],
    )).map((row) => [
      rowString(row, "topic"),
      Schema.decodeUnknownSync(Schema.Array(Schema.Int))(JSON.parse(rowString(row, "receipts"))),
    ]));
    const lore = yield* ai.object("search", [
      {
        content: "Extract durable friend-group lore. Return kebab-case topics, concise summaries, and only message IDs present in the text as receipts.",
        role: "system",
      },
      {
        content: messages.map((message) =>
          `${message.messageId} ${message.createTime} ${message.author}: ${message.text}`).join("\n"),
        role: "user",
      },
    ], Lore, { maxTokens: 3_000 });
    const allowed = new Set(messages.map((message) => message.messageId));
    for (const item of lore.items) {
      if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(item.topic)) continue;
      const receipts = [...new Set([
        ...(storedLore.get(item.topic) ?? []),
        ...item.receipts.filter((id) => allowed.has(id)),
      ])];
      yield* dependencies.database.execute(
        `INSERT INTO chat_lore (
          chat_id, topic, summary, receipts, source_end_message_id, update_time
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, topic) DO UPDATE SET
          summary = excluded.summary, receipts = excluded.receipts,
          source_end_message_id = excluded.source_end_message_id,
          update_time = CURRENT_TIMESTAMP`,
        [chatId, item.topic, item.summary, JSON.stringify(receipts), rowNumber(windows[0]!, "end_message_id")],
      );
    }
  });
}

export function searchFeature(dependencies: AppDependencies) {
  const ai = new Ai(dependencies);
  const index = Effect.fn("searchIndexWorker")(function* (chatIds?: ReadonlyArray<number>) {
    const ids = chatIds ?? (yield* dependencies.database.all(
      "SELECT chat_id FROM group_settings WHERE fts = 1 ORDER BY chat_id",
    )).map((chat) => rowNumber(chat, "chat_id"));
    for (const chatId of ids) yield* indexChat(dependencies, ai, chatId).pipe(
      Effect.tapCause((cause) => Effect.logError("Search indexing failed", { chatId, cause })),
    );
    yield* syncSearchStores(dependencies, ids);
  });
  // Needs the bot, so the scheduler runs it after indexing; the operator CLI
  // only indexes.
  const membership = Effect.fn("searchMembershipWorker")(function* (chatIds?: ReadonlyArray<number>) {
    const ids = chatIds ?? (yield* dependencies.database.all(
      "SELECT chat_id FROM group_settings WHERE fts = 1 ORDER BY chat_id",
    )).map((chat) => rowNumber(chat, "chat_id"));
    for (const chatId of ids) yield* refreshSearchMembership(dependencies.config.stateDirectory, chatId).pipe(
      Effect.catchCause((cause) => Effect.logError("Search membership refresh failed", { chatId, cause })),
    );
  });
  const memory = Effect.fn("chatMemoryWorker")(function* (chatIds?: ReadonlyArray<number>) {
    const ids = chatIds ?? (yield* dependencies.database.all(
      "SELECT chat_id FROM group_settings WHERE fts = 1 ORDER BY chat_id",
    )).map((chat) => rowNumber(chat, "chat_id"));
    for (const chatId of ids) yield* buildMemory(dependencies, ai, chatId).pipe(
      Effect.tapCause((cause) => Effect.logError("Search memory failed", { chatId, cause })),
    );
  });
  return {
    commands: [searchCommand(dependencies), enableCommand(dependencies), importCommand(dependencies)] as const,
    workers: { index, membership, memory },
  };
}
