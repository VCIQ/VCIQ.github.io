import { technologyTopicDefinitions } from "@/lib/technology-topics";

function normalizeTechnologyText(value: string) {
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
  const normalizedTerm = normalizeTechnologyText(term);
  if (normalizedTerm.length < 2) return false;

  const rawTerm = normalizedSearchText(term).trim();
  const shortAsciiToken = /^[a-z0-9]+$/u.test(rawTerm) && rawTerm.length <= 4;
  if (shortAsciiToken) {
    const tokenPattern = new RegExp(
      `(^|[^a-z0-9])${escapeRegExp(rawTerm)}([^a-z0-9]|$)`,
      "iu",
    );
    return tokenPattern.test(normalizedSearchText(corpus));
  }

  return normalizeTechnologyText(corpus).includes(normalizedTerm);
}

export function technologyTopicsForText(
  values: Array<string | undefined | null>,
) {
  const corpus = values.filter(Boolean).join(" ");
  if (!normalizeTechnologyText(corpus)) return [];

  return technologyTopicDefinitions.filter((topic) =>
    topic.matchTerms.some((term) => technologyTermMatchesText(corpus, term)),
  );
}
