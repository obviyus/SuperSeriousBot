import type { Message, Update } from "telly";

// Telly runs updates with the same conversation key in order, and the default
// key is the chat. A generation command can take a minute, so it would hold up
// every later message in its chat. These commands get their own key instead.
// They are not tracked into chat_stats, so running them out of order is safe.
const slowCommands = new Set([
  "ask",
  "based",
  "dl",
  "edit",
  "search",
  "song",
  "tldr",
  "tldw",
  "tr",
  "video",
]);

function commandName(message: Message): string | undefined {
  const text = message.text ?? message.caption;
  const entity = (message.entities ?? message.captionEntities)?.[0];
  if (text === undefined || entity?.type !== "bot_command" || entity.offset !== 0) return undefined;
  return text.slice(1, entity.length).split("@")[0]?.toLowerCase();
}

function chatId(update: Update): number | string | undefined {
  const message = update.message ?? update.editedMessage ?? update.channelPost ??
    update.editedChannelPost ?? update.businessMessage ?? update.editedBusinessMessage;
  if (message !== undefined) return message.chat.id;
  if (update.callbackQuery?.message !== undefined) return update.callbackQuery.message.chat.id;
  if (update.callbackQuery !== undefined) return `instance:${update.callbackQuery.chatInstance}`;
  return (update.messageReaction ?? update.messageReactionCount ?? update.chatJoinRequest ??
    update.myChatMember ?? update.chatMember ?? update.chatBoost ?? update.removedChatBoost)?.chat.id;
}

export function conversationKey(update: Update): string {
  const chat = chatId(update);
  if (chat === undefined) return `update:${update.updateId}`;
  const command = update.message === undefined ? undefined : commandName(update.message);
  return command !== undefined && slowCommands.has(command)
    ? `chat:${chat}:update:${update.updateId}`
    : `chat:${chat}`;
}
