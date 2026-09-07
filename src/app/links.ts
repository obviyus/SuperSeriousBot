export function messageLink(chatId: number, messageId: number, username?: string): string | undefined {
  if (username !== undefined) return `https://t.me/${username}/${messageId}`;
  const id = String(chatId);
  return id.startsWith("-100") ? `https://t.me/c/${id.slice(4)}/${messageId}` : undefined;
}
