export function canonicalPublicHttpUrl(value: unknown): string {
  const raw = String(value ?? "")
    .replace(/\\+$/gu, "")
    .trim();
  if (!raw) return "";

  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" && url.protocol !== "https:") return "";
    return url.toString();
  } catch {
    return "";
  }
}
