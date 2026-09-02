export function truncate(text: string, maximum: number): string {
  const normalized = text.trim();
  return normalized.length > maximum ? `${normalized.slice(0, maximum)}...` : normalized;
}

export function stripHtml(text: string): string {
  return text
    .replace(/<br\s*\/?>/giu, "\n")
    .replace(/<[^>]+>/gu, "")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .trim();
}
