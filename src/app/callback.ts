import {
  answerCallback,
  Effect,
  on,
  type Bot,
  type BotApiError,
  type CallbackQueryMatch,
  type Filter,
} from "telly";

export function callbackRoute<A extends CallbackQueryMatch>(
  name: string,
  filter: Filter<A>,
  handle: (match: A) => Effect.Effect<unknown, unknown, Bot>,
) {
  const recover = (query: A["callbackQuery"]) =>
    Effect.logError("Callback failed").pipe(
      Effect.annotateLogs({ callback: name }),
      Effect.andThen(answerCallback(query, { text: "Something went wrong. Please try again." })),
    );
  return on(filter, (match) => handle(match).pipe(
    Effect.catch(() => recover(match.callbackQuery)),
    Effect.catchDefect(() => recover(match.callbackQuery)),
  ));
}

export function ignoreUnchangedMessage<A, R>(
  effect: Effect.Effect<A, BotApiError, R>,
): Effect.Effect<A | void, BotApiError, R> {
  return effect.pipe(Effect.catch((error) =>
    error.reason._tag === "TelegramRejected" &&
      error.reason.description.toLowerCase().includes("message is not modified")
      ? Effect.void
      : Effect.fail(error)));
}
