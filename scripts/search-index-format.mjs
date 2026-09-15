const NAMED_HTML_ENTITIES = new Map([
  ["nbsp", " "],
  ["amp", "&"],
  ["quot", '"'],
  ["apos", "'"],
  ["lt", "<"],
  ["gt", ">"],
  ["hellip", "…"],
  ["ldquo", "“"],
  ["rdquo", "”"],
  ["lsquo", "‘"],
  ["rsquo", "’"],
]);

function decodeHtmlEntityToken(token) {
  const lowered = token.toLowerCase();
  if (NAMED_HTML_ENTITIES.has(lowered)) return NAMED_HTML_ENTITIES.get(lowered);

  if (/^#x[0-9a-f]+$/i.test(token)) {
    const codePoint = Number.parseInt(token.slice(2), 16);
    if (Number.isInteger(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff) {
      return String.fromCodePoint(codePoint);
    }
  }

  if (/^#\d+$/.test(token)) {
    const codePoint = Number.parseInt(token.slice(1), 10);
    if (Number.isInteger(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff) {
      return String.fromCodePoint(codePoint);
    }
  }

  return `&${token};`;
}

export function cleanSearchText(value, maxLength = 320) {
  if (typeof value !== "string") return "";
  return value
    .replace(/&(#x[0-9a-f]+|#\d+|nbsp|amp|quot|apos|lt|gt|hellip|ldquo|rdquo|lsquo|rsquo);/gi, (_, token) => decodeHtmlEntityToken(token))
    .replace(/<[^>]*>/g, " ")
    .normalize("NFKC")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}

export function formatSearchDate(value) {
  const cleaned = cleanSearchText(value, 80);
  if (!cleaned) return "";

  const isoDate = cleaned.match(/^(\d{4}-\d{2}-\d{2})/u)?.[1];
  if (isoDate) return isoDate;

  const parsed = Date.parse(cleaned);
  return Number.isFinite(parsed)
    ? new Date(parsed).toISOString().slice(0, 10)
    : cleanSearchText(cleaned, 10);
}
