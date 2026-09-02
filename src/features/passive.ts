import {
  Effect,
  Filter,
  on,
  regex,
  repliedMessage,
  reply,
  routes,
  setMessageReaction,
  type UpdateHandler,
} from "telly";

import type { AppDependencies } from "../app/dependencies.ts";

const reactions = {
  "bad bot": ["😨", "😭", "💔", "😢", "😱"],
  "good bot": ["💘", "🥰", "❤‍🔥", "🍌", "💋", "👨‍💻", "💅", "😘", "👾"],
} as const;

export const sedHandler = routes(on(
  Filter.and(repliedMessage(), regex(/^s\/[\s\S]*\/[\s\S]*/u)),
  ([{ repliedMessage: source }, { text }]) => {
    if (source.text === undefined) return Effect.void;
    const separator = text.indexOf("/", 2);
    if (separator === -1) return Effect.void;
    const search = text.slice(2, separator);
    const replacement = text.slice(separator + 1);
    return reply(source, source.text.replaceAll(search, () => replacement));
  },
));

export function reactionHandler(dependencies: AppDependencies): UpdateHandler<never, void> {
  return Effect.fn("reactionHandler")(function* (update) {
    const message = update.message;
    if (message?.text === undefined) return;
    const normalized = message.text.toLowerCase();
    const entry = Object.entries(reactions).find(([trigger]) => normalized.includes(trigger));
    if (entry === undefined) return;
    const choices = entry[1];
    const index = Math.min(choices.length - 1, Math.floor(dependencies.random() * choices.length));
    yield* setMessageReaction({
      chatId: message.chat.id,
      messageId: message.messageId,
      reaction: [{ emoji: choices[index] ?? choices[0], type: "emoji" }],
    }).pipe(Effect.catch(() => Effect.void));
  });
}
