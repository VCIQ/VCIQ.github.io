import { technologyTopicDefinitions } from "@/lib/technology-topics";

function normalizeTechnologyText(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

export function technologyTopicsForText(
  values: Array<string | undefined | null>,
) {
  const corpus = values.filter(Boolean).join(" ");
  const normalizedCorpus = normalizeTechnologyText(corpus);
  if (!normalizedCorpus) return [];

  return technologyTopicDefinitions.filter((topic) =>
    topic.matchTerms.some((term) => {
      const normalizedTerm = normalizeTechnologyText(term);
      return normalizedTerm.length >= 2 && normalizedCorpus.includes(normalizedTerm);
    }),
  );
}
