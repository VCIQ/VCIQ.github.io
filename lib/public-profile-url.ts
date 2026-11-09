/** Public HTTPS sources only; credentials and nonstandard ports are never accepted. */
export function safePublicUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password && (!u.port || u.port === "443") &&
      /\.[a-z]{2,}$/i.test(u.hostname) && !/\.(local|internal|localhost)$/i.test(u.hostname);
  } catch { return false; }
}

/** A canonical profile URL is an identifier, never evidence of an investment or friendship. */
export function normalizeLinkedInProfile(value: string): string | null {
  try {
    const u = new URL(value);
    if (!safePublicUrl(value) || !/^(?:[a-z]{2,3}\.)?linkedin\.com$/i.test(u.hostname) ||
        !/^\/in\/[^/]+\/?$/.test(u.pathname) || /%2f|%5c/i.test(u.pathname)) return null;
    return `https://www.linkedin.com${u.pathname.replace(/\/$/, "")}`;
  } catch { return null; }
}
