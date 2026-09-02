import {
  deleteMessage,
  downloadFile,
  editMessageText,
  Effect,
  getChatAdministrators,
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
import { replyRich, richMarkdownPrompt } from "../app/rich.ts";
import { getModel, normalizeModelName } from "./settings.ts";

const embeddingModel = "qwen/qwen3-embedding-8b";
const noAnswer = "No solid answer in the chat.";
const SearchAnswer = Schema.Struct({
  answer: Schema.String,
  citations: Schema.Array(Schema.Int),
});
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

interface SearchEvidence extends SearchWindow {
  readonly citationMessageId: number;
  readonly score: number;
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
  const groups: Array<Array<SourceMessage>> = [];
  let current: Array<SourceMessage> = [];
  for (const message of messages) {
    const previous = current.at(-1);
    const gap = previous === undefined
      ? 0
      : new Date(message.createTime).getTime() - new Date(previous.createTime).getTime();
    if (previous !== undefined && (previous.userId !== message.userId || gap > 300_000 || current.length === 12)) {
      groups.push(current);
      current = [];
    }
    current.push(message);
  }
  if (current.length > 0) groups.push(current);
  return groups.map((group) => {
    const first = group[0];
    const last = group.at(-1);
    if (first === undefined || last === undefined) throw new Error("Empty utterance group");
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

function sourceMessages(dependencies: AppDependencies, chatId: number) {
  return dependencies.database.all(
    `SELECT messages.message_id, messages.user_id, messages.create_time,
            COALESCE(users.username, 'user:' || messages.user_id) AS author,
            messages.message_text
     FROM chat_stats messages
     LEFT JOIN user_stats users ON users.user_id = messages.user_id
     WHERE messages.chat_id = ? AND messages.message_id IS NOT NULL
       AND messages.message_text IS NOT NULL AND messages.message_text != ''
       AND messages.message_text NOT LIKE '/%'
     ORDER BY messages.message_id`,
    [chatId],
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

function vectorJson(values: ReadonlyArray<number>): string {
  return JSON.stringify(values);
}

function indexChat(dependencies: AppDependencies, ai: Ai, chatId: number) {
  return Effect.gen(function* () {
    const messages = yield* sourceMessages(dependencies, chatId);
    const windows = buildWindows(messages);
    const utterances = buildUtterances(messages);
    for (const batch of Array.from({ length: Math.ceil(windows.length / 64) }, (_, index) =>
      windows.slice(index * 64, index * 64 + 64))) {
      const missing = [] as Array<SearchWindow>;
      for (const window of batch) {
        const exists = yield* dependencies.database.one(
          `SELECT 1 FROM chat_search_windows
           WHERE chat_id = ? AND start_message_id = ? AND end_message_id = ?
             AND embedding_model = ? AND embedding_dimension = 1024`,
          [chatId, window.startMessageId, window.endMessageId, embeddingModel],
        );
        if (exists === undefined) missing.push(window);
      }
      if (missing.length === 0) continue;
      const embeddings = yield* ai.embeddings(missing.map((window) => window.text), 1_024);
      yield* Effect.forEach(missing, (window, index) => Effect.gen(function* () {
        yield* dependencies.database.execute(
          `INSERT OR REPLACE INTO chat_search_windows (
            chat_id, start_message_id, end_message_id, start_time, end_time,
            message_count, message_text, embedding, embedding_model, embedding_dimension
          ) VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 1024)`,
          [
            chatId,
            window.startMessageId,
            window.endMessageId,
            window.startTime,
            window.endTime,
            window.messageCount,
            window.text,
            vectorJson(embeddings[index] ?? []),
            embeddingModel,
          ],
        );
        yield* dependencies.database.execute(
          `DELETE FROM chat_search_windows
           WHERE chat_id = ? AND start_message_id = ? AND end_message_id < ?
             AND embedding_model = ? AND embedding_dimension = 1024`,
          [chatId, window.startMessageId, window.endMessageId, embeddingModel],
        );
      }), { concurrency: 1, discard: true });
    }
    for (const batch of Array.from({ length: Math.ceil(utterances.length / 64) }, (_, index) =>
      utterances.slice(index * 64, index * 64 + 64))) {
      const missing = [] as Array<(typeof utterances)[number]>;
      for (const utterance of batch) {
        const exists = yield* dependencies.database.one(
          `SELECT 1 FROM chat_search_utterances
           WHERE chat_id = ? AND start_message_id = ? AND end_message_id = ?
             AND embedding_model = ? AND embedding_dimension = 256`,
          [chatId, utterance.startMessageId, utterance.endMessageId, embeddingModel],
        );
        if (exists === undefined) missing.push(utterance);
      }
      if (missing.length === 0) continue;
      const embeddings = yield* ai.embeddings(missing.map((item) => item.text), 256);
      yield* Effect.forEach(missing, (item, index) => dependencies.database.execute(
        `INSERT OR REPLACE INTO chat_search_utterances (
          chat_id, start_message_id, end_message_id, user_id, author, start_time,
          end_time, message_count, message_text, embedding, embedding_model, embedding_dimension
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, vector32(?), ?, 256)`,
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
          vectorJson(embeddings[index] ?? []),
          embeddingModel,
        ],
      ), { concurrency: 1, discard: true });
    }
  });
}

function evidenceFromWindows(
  dependencies: AppDependencies,
  chatId: number,
  vector: ReadonlyArray<number>,
  authorId?: number,
) {
  return dependencies.database.all(
    `SELECT windows.start_message_id, windows.end_message_id,
            windows.start_time, windows.end_time, windows.message_count,
            windows.message_text,
            1 - vector_distance_cos(windows.embedding, vector32(?)) AS score
     FROM chat_search_windows windows
     WHERE windows.chat_id = ? AND windows.embedding_model = ?
       AND windows.embedding_dimension = 1024
       ${authorId === undefined ? "" : `AND EXISTS (
         SELECT 1 FROM chat_stats messages
         WHERE messages.chat_id = windows.chat_id
           AND messages.message_id BETWEEN windows.start_message_id AND windows.end_message_id
           AND messages.user_id = ?
       )`}
     ORDER BY score DESC LIMIT 12`,
    authorId === undefined
      ? [vectorJson(vector), chatId, embeddingModel]
      : [vectorJson(vector), chatId, embeddingModel, authorId],
  ).pipe(Effect.map((rows): ReadonlyArray<SearchEvidence> => rows.map((row) => ({
    citationMessageId: rowNumber(row, "end_message_id"),
    endMessageId: rowNumber(row, "end_message_id"),
    endTime: rowString(row, "end_time"),
    messageCount: rowNumber(row, "message_count"),
    score: Number(row["score"]),
    startMessageId: rowNumber(row, "start_message_id"),
    startTime: rowString(row, "start_time"),
    text: rowString(row, "message_text"),
  }))));
}

function overlaps(left: SearchEvidence, right: SearchEvidence): boolean {
  return left.startMessageId <= right.endMessageId && right.startMessageId <= left.endMessageId;
}

export function selectEvidence(values: ReadonlyArray<SearchEvidence>): ReadonlyArray<SearchEvidence> {
  const selected: Array<SearchEvidence> = [];
  for (const value of [...values].sort((left, right) => right.score - left.score)) {
    if (selected.some((current) => overlaps(value, current))) continue;
    selected.push(value);
    if (selected.length === 6) break;
  }
  return selected;
}

function messageLink(chatId: number, messageId: number): string | undefined {
  const value = String(chatId);
  return value.startsWith("-100") ? `https://t.me/c/${value.slice(4)}/${messageId}` : undefined;
}

export function renderSearchAnswer(
  output: typeof SearchAnswer.Type,
  evidence: ReadonlyArray<SearchEvidence>,
  chatId: number,
): { readonly answer: string; readonly citations: ReadonlyArray<number> } {
  const answer = output.answer.trim();
  const indexes = [...new Set(output.citations)];
  if (answer.length === 0 || answer === noAnswer || indexes.some((index) =>
    index < 1 || index > evidence.length)) return { answer: noAnswer, citations: [] };
  const citations = indexes.flatMap((index) => {
    const item = evidence[index - 1];
    return item === undefined ? [] : [item.citationMessageId];
  });
  const links = citations.flatMap((messageId, index) => {
    const link = messageLink(chatId, messageId);
    return link === undefined ? [] : [`[${indexes[index]}](${link})`];
  });
  return links.length === 0
    ? { answer: noAnswer, citations: [] }
    : { answer: `${answer}\n\n${links.join(" ")}`, citations };
}

function canModerate(dependencies: AppDependencies, chatId: number, userId: number, privateChat: boolean) {
  if (privateChat || isAdmin(dependencies, userId)) return Effect.succeed(true);
  return getChatAdministrators({ chatId }).pipe(
    Effect.map((members) => members.some((member) => member.user.id === userId)),
  );
}

function searchCommand(dependencies: AppDependencies, ai: Ai): CommandDefinition {
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
      const result = yield* Effect.gen(function* () {
        const vectors = yield* ai.embeddings([
          `Instruct: Retrieve Telegram chat evidence needed to answer the question.\nQuery: ${match.argText}`,
        ], 1_024);
        const evidence = selectEvidence(yield* evidenceFromWindows(
          dependencies,
          match.message.chat.id,
          vectors[0] ?? [],
          match.message.replyToMessage?.from?.id,
        ));
        if (evidence.length === 0) return { answer: noAnswer, citations: [] };
        const personas = yield* dependencies.database.all(
          "SELECT user_id, sheet, receipts FROM chat_personas WHERE chat_id = ? ORDER BY user_id",
          [match.message.chat.id],
        );
        const lore = yield* dependencies.database.all(
          "SELECT topic, summary, receipts FROM chat_lore WHERE chat_id = ? ORDER BY topic",
          [match.message.chat.id],
        );
        const context = [
          ...personas.map((row) => `[Persona user:${rowNumber(row, "user_id")}]\n${rowString(row, "sheet")}`),
          ...lore.map((row) => `[Lore: ${rowString(row, "topic")}]\n${rowString(row, "summary")}`),
          ...evidence.map((item, index) => `[Evidence ${index + 1}]\n${item.text}`),
        ].join("\n\n").slice(0, 240_000);
        const output = yield* ai.object("search", [
          { content: richMarkdownPrompt, role: "system" },
          {
            content: `Answer in one to three sentences using only supplied evidence. Return ${noAnswer} when evidence is insufficient. citations must list every evidence number that directly supports the answer.`,
            role: "system",
          },
          { content: `Question: ${match.argText}\n\n${context}`, role: "user" },
        ], SearchAnswer, { maxTokens: 500 });
        return renderSearchAnswer(output, evidence, match.message.chat.id);
      }).pipe(
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'fact')`,
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
      for (const batch of Array.from({ length: Math.ceil(rows.length / 200) }, (_, index) =>
        rows.slice(index * 200, index * 200 + 200))) {
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
    const members = yield* dependencies.database.all(
      `SELECT utterances.user_id, COALESCE(users.username, 'user:' || utterances.user_id) AS username,
              COUNT(*) AS count, MAX(utterances.end_message_id) AS end_message_id
       FROM chat_search_utterances utterances
       LEFT JOIN user_stats users ON users.user_id = utterances.user_id
       WHERE utterances.chat_id = ?
       GROUP BY utterances.user_id HAVING count >= 200`,
      [chatId],
    );
    for (const member of members) {
      const userId = rowNumber(member, "user_id");
      const utterances = yield* dependencies.database.all(
        `SELECT end_message_id, end_time, author, message_text
         FROM chat_search_utterances WHERE chat_id = ? AND user_id = ?
         ORDER BY end_message_id DESC LIMIT 400`,
        [chatId, userId],
      );
      const context = [...utterances].reverse().map((row) =>
        `${rowNumber(row, "end_message_id")} ${rowString(row, "end_time")} ${rowString(row, "author")}: ${rowString(row, "message_text").replaceAll("\n", " / ")}`
      ).join("\n").slice(0, 180_000);
      const persona = yield* ai.object("search", [
        {
          content: "Write a concise friend-group persona dossier using only the supplied messages. Include concrete traits and short verbatim receipts. Also return aliases used for this member with confidence from 0 to 1.",
          role: "system",
        },
        { content: context, role: "user" },
      ], Persona, { maxTokens: 2_000, model: "openai/gpt-5.6-luna" });
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
      `SELECT end_message_id, message_text FROM chat_search_windows
       WHERE chat_id = ? ORDER BY end_message_id DESC LIMIT 100`,
      [chatId],
    );
    if (windows.length === 0) return;
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
      { content: [...windows].reverse().map((row) => rowString(row, "message_text")).join("\n\n").slice(0, 240_000), role: "user" },
    ], Lore, { maxTokens: 3_000, model: "openai/gpt-5.6-luna" });
    const allowed = new Set(windows.flatMap((row) =>
      rowString(row, "message_text").match(/^\d+/gmu)?.map(Number) ?? []));
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
    for (const chatId of ids) yield* indexChat(dependencies, ai, chatId);
  });
  const memory = Effect.fn("chatMemoryWorker")(function* (chatIds?: ReadonlyArray<number>) {
    const ids = chatIds ?? (yield* dependencies.database.all(
      "SELECT chat_id FROM group_settings WHERE fts = 1 ORDER BY chat_id",
    )).map((chat) => rowNumber(chat, "chat_id"));
    for (const chatId of ids) yield* buildMemory(dependencies, ai, chatId);
  });
  return {
    commands: [searchCommand(dependencies, ai), enableCommand(dependencies), importCommand(dependencies)] as const,
    workers: { index, memory },
  };
}
