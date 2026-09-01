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
import type { AppDependencies } from "./dependencies.ts";

export type CommandEffect = Effect.Effect<unknown, unknown, Bot>;

export interface CommandDefinition {
  readonly apiKey?: keyof ApiConfig;
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
      status, duration_ms, error_type, error_message
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
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
    ],
  ).pipe(
    Effect.catch((failure) => Effect.logError("Failed to record command").pipe(
      Effect.annotateLogs({ operation: failure.operation }),
    )),
    Effect.asVoid,
  );
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
      const run = Effect.gen(function* () {
        yield* commandPresence(match.message);
        if (!enabled(definition, dependencies)) {
          return yield* answer(match.message, "❌ This command is disabled.");
        }
        if (user !== undefined && (yield* isBlocked(dependencies, user.id, commandName(match)))) {
          status = "blocked";
          return yield* answer(match.message, "❌ You are blocked from using this command.");
        }
        return yield* definition.run(match);
      }).pipe(
        Effect.catch((error) => {
          status = "failed";
          commandError = error;
          return Effect.logError("Command failed").pipe(
            Effect.annotateLogs({ command: commandName(match) }),
            Effect.andThen(answer(match.message, "Something went wrong. Please try again.")),
          );
        }),
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
