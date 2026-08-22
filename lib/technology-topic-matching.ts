import { technologyTermMatchesText } from "@/lib/technology-term-matching";
import { technologyTopicDefinitions } from "@/lib/technology-topics";

export function technologyTopicsForText(
  values: Array<string | undefined | null>,
) {
  const corpus = values.filter(Boolean).join(" ");
  if (!corpus.trim()) return [];

  return technologyTopicDefinitions.filter((topic) =>
    topic.matchTerms.some((term) => technologyTermMatchesText(corpus, term)),
  );
}
