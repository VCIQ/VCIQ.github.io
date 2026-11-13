/**
 * Classify public WeChat article URLs without rewriting source identity.
 * "durable" refers only to a recognizable shareable URL structure, not an
 * online availability guarantee or verification of the publisher.
 */
const SHORT_CODE = /^\/s\/[A-Za-z0-9_-]+$/u;
const TEMPORARY_KEYS = new Set(["signature", "timestamp"]);

export type WeChatLinkKind = "durable" | "temporary" | "unverified" | "other";

export function classifyWeChatArticleUrl(input: string): WeChatLinkKind {
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    return "other";
  }
  if (url.hostname.toLowerCase() !== "mp.weixin.qq.com" ||
      !(url.pathname === "/s" || url.pathname.startsWith("/s/"))) {
    return "other";
  }
  if (url.protocol !== "https:" || url.username || url.password ||
      (url.port && url.port !== "443") || url.hash) return "unverified";
  const keys = [...url.searchParams.keys()].map((key) => key.toLowerCase());
  if (keys.some((key) => TEMPORARY_KEYS.has(key)) ||
      ["src", "ver", "new"].every((key) => keys.includes(key))) return "temporary";
  if (SHORT_CODE.test(url.pathname)) return "durable";
  if (url.pathname !== "/s") return "unverified";
  const identity = ["__biz", "mid", "idx", "sn"];
  if (!identity.every((key) => url.searchParams.getAll(key).length === 1 &&
      Boolean(url.searchParams.get(key)))) return "unverified";
  if (!/^\d+$/u.test(url.searchParams.get("mid") ?? "") ||
      !/^\d+$/u.test(url.searchParams.get("idx") ?? "")) return "unverified";
  return "durable";
}

export function isNonDurableWeChatArticleUrl(input: string): boolean {
  const kind = classifyWeChatArticleUrl(input);
  return kind === "temporary" || kind === "unverified";
}
