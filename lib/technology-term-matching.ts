export function normalizeTechnologyTerm(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function normalizedSearchText(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("zh-CN");
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

export function technologyTermMatchesText(corpus: string, term: string) {
  const normalizedTerm = normalizeTechnologyTerm(term);
  if (normalizedTerm.length < 2) return false;

  const rawTerm = normalizedSearchText(term).trim();
  const shortAsciiToken = /^[a-z0-9]+$/u.test(rawTerm) && rawTerm.length <= 3;
  if (shortAsciiToken) {
    const tokenPattern = new RegExp(
      `(^|[^a-z0-9])${escapeRegExp(rawTerm)}([^a-z0-9]|$)`,
      "iu",
    );
    return tokenPattern.test(normalizedSearchText(corpus));
  }

  return normalizeTechnologyTerm(corpus).includes(normalizedTerm);
}
