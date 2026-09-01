import {
  Effect,
  html,
  reply,
  respond,
  respondTo,
  sendChatAction,
  setMessageReaction,
  type Bot,
  type BotApiError,
  type CommandMatch,
  type ConversationMessage,
  type ConversationMessageOptions,
  type Message,
} from "telly";

import type { ApiConfig } from "./config.ts";
import { isAdmin } from "./admin.ts";
import type { AppDependencies } from "./dependencies.ts";

export type CommandEffect = Effect.Effect<unknown, unknown, Bot>;

export interface CommandDefinition {
  readonly apiKey?: keyof ApiConfig;
  readonly availability?: "whitelist" | "whitelist-private";
  readonly dailyLimit?: number;
  readonly description: string;
  readonly example: string;
  readonly names: readonly [string, ...ReadonlyArray<string>];
  readonly run: (match: CommandMatch) => CommandEffect;
  readonly usage: string;
}

export function answer(
  message: ConversationMessage,
  input: string | ConversationMessageOptions,
): Effect.Effect<Message, BotApiError, Bot> {
  return message.chat.type === "private" ? respond(message, input) : reply(message, input);
}

export function usage(
  message: ConversationMessage,
  definition: Pick<CommandDefinition, "description" | "example" | "usage">,
) {
  return answer(message, {
    linkPreviewOptions: { isDisabled: true },
    parseMode: "HTML",
    text: `${html.escape(definition.description)}\n\n<b>Usage:</b>\n<pre>${html.escape(definition.usage)}</pre>\n\n<b>Example:</b>\n<pre>${html.escape(definition.example)}</pre>`,
  });
}

function enabled(definition: CommandDefinition, dependencies: AppDependencies): boolean {
  return definition.apiKey === undefined || dependencies.config.api[definition.apiKey] !== undefined;
}

function commandName(match: CommandMatch): string {
  return match.command.toLowerCase();
}

function commandPresence(message: Message) {
  return Effect.all([
    sendChatAction({ ...respondTo(message), action: "typing" }),
    setMessageReaction({
      chatId: message.chat.id,
      messageId: message.messageId,
      reaction: [{ emoji: "✍", type: "emoji" }],
    }),
  ], { concurrency: "unbounded", discard: true }).pipe(
    Effect.catch(() => Effect.void),
  );
}

function isBlocked(dependencies: AppDependencies, userId: number, name: string) {
  return dependencies.database.one(
    "SELECT 1 FROM command_blocklist WHERE user_id = ? AND command = ?",
    [userId, name],
  ).pipe(Effect.map((row) => row !== undefined));
}

function ensureAvailable(
  definition: CommandDefinition,
  dependencies: AppDependencies,
  match: CommandMatch,
) {
  const user = match.message.from;
  if (definition.availability === undefined || user === undefined || isAdmin(dependencies, user.id)) {
    return Effect.succeed(true);
  }
  if (match.message.chat.type === "private" && definition.availability !== "whitelist-private") {
    return answer(match.message, "This command is not available in private chats.").pipe(
      Effect.as(false),
    );
  }
  return dependencies.database.one(
    `SELECT 1 FROM command_whitelist
     WHERE command = ? AND (
       (whitelist_type = 'chat' AND whitelist_id = ?)
       OR (whitelist_type = 'user' AND whitelist_id = ?)
     )`,
    [
      commandName(match),
      match.message.chat.type === "private" ? user.id : match.message.chat.id,
      user.id,
    ],
  ).pipe(
    Effect.flatMap((row) => row !== undefined
      ? Effect.succeed(true)
      : answer(
          match.message,
          match.message.chat.type === "private"
            ? "This command is not available in private chats."
            : "This command is not available in this chat. Please contact an admin to whitelist this command.",
        ).pipe(Effect.as(false))),
  );
}

function recordCommand(
  dependencies: AppDependencies,
  match: CommandMatch,
  status: "blocked" | "completed" | "failed",
  start: number,
  error?: unknown,
) {
  const user = match.message.from;
  if (user === undefined) return Effect.void;
  return dependencies.database.execute(
    `INSERT INTO command_stats (
      command, user_id, chat_id, message_id, username, input_text,
      status, duration_ms, error_type, error_message, error_traceback
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      commandName(match),
      user.id,
      match.message.chat.id,
      match.message.messageId,
      user.username === undefined ? user.firstName : `@${user.username}`,
      match.argText.length === 0 ? null : match.argText,
      status,
      Math.max(0, Math.round(dependencies.monotonicMilliseconds() - start)),
      error instanceof Error ? error.name : null,
      error instanceof Error ? error.message : error === undefined ? null : String(error),
      error instanceof Error ? error.stack ?? null : null,
    ],
  ).pipe(
    Effect.catch((failure) => Effect.logError("Failed to record command").pipe(
      Effect.annotateLogs({ operation: failure.operation }),
    )),
    Effect.asVoid,
  );
}

function consumeQuota(
  definition: CommandDefinition,
  dependencies: AppDependencies,
  match: CommandMatch,
) {
  const user = match.message.from;
  if (
    definition.dailyLimit === undefined ||
    user === undefined ||
    isAdmin(dependencies, user.id)
  ) return Effect.succeed(true);
  return dependencies.database.execute(
    `INSERT INTO user_command_limits (user_id, command, \`limit\`, current_usage)
     VALUES (?, ?, ?, 1)
     ON CONFLICT(user_id, command) DO UPDATE SET
       current_usage = current_usage + 1
     WHERE current_usage < \`limit\``,
    [user.id, commandName(match), definition.dailyLimit],
  ).pipe(
    Effect.flatMap((result) => result.rowsAffected > 0
      ? Effect.succeed(true)
      : answer(
          match.message,
          "Daily limit for this command reached. Try again tomorrow.",
        ).pipe(Effect.as(false))),
  );
}

export function resetCommandLimits(dependencies: AppDependencies) {
  return dependencies.database.execute(
    "UPDATE user_command_limits SET current_usage = 0 WHERE current_usage > 0",
  ).pipe(Effect.asVoid);
}

export function commandHandlers(
  definitions: ReadonlyArray<CommandDefinition>,
  dependencies: AppDependencies,
): Readonly<Record<string, (match: CommandMatch) => CommandEffect>> {
  const handlers: Record<string, (match: CommandMatch) => CommandEffect> = {};
  for (const definition of definitions) {
    const handle = Effect.fn(`command.${definition.names[0]}`)(function* (match: CommandMatch) {
      const start = dependencies.monotonicMilliseconds();
      let status: "blocked" | "completed" | "failed" = "completed";
      let commandError: unknown;
      const user = match.message.from;
      const recover = (error: unknown) => {
        status = "failed";
        commandError = error;
        return Effect.logError("Command failed").pipe(
          Effect.annotateLogs({ command: commandName(match) }),
          Effect.andThen(answer(match.message, "Something went wrong. Please try again.")),
        );
      };
      const run = Effect.gen(function* () {
        if (!enabled(definition, dependencies)) {
          return yield* answer(match.message, "❌ This command is disabled.");
        }
        if (user !== undefined && (yield* isBlocked(dependencies, user.id, commandName(match)))) {
          status = "blocked";
          return yield* answer(match.message, "❌ You are blocked from using this command.");
        }
        if (!(yield* ensureAvailable(definition, dependencies, match))) return;
        if (!(yield* consumeQuota(definition, dependencies, match))) return;
        yield* commandPresence(match.message);
        return yield* definition.run(match);
      }).pipe(
        Effect.catch(recover),
        Effect.catchDefect(recover),
        Effect.ensuring(
          Effect.suspend(() => recordCommand(
            dependencies,
            match,
            status,
            start,
            commandError,
          )),
        ),
      );
      return yield* run;
    });
    for (const name of definition.names) handlers[name] = handle;
  }
  return handlers;
}

export function botCommands(
  definitions: ReadonlyArray<CommandDefinition>,
  dependencies: AppDependencies,
) {
  return definitions.filter((definition) => enabled(definition, dependencies)).map((definition) => ({
    command: definition.names[0],
    description: definition.description,
  }));
}
