import { technologyTermMatchesText } from "@/lib/technology-term-matching";
import {
  technologyTopicDefinitions,
  technologyTopicsForTrack,
} from "@/lib/technology-topics";

export function technologyTopicsForText(
  values: Array<string | undefined | null>,
) {
  const corpus = values.filter(Boolean).join(" ");
  if (!corpus.trim()) return [];

  return technologyTopicDefinitions.filter((topic) =>
    topic.matchTerms.some((term) => technologyTermMatchesText(corpus, term)),
  );
}

export function technologyTopicsForTextInTrack(
  values: Array<string | undefined | null>,
  trackName: string,
) {
  const allowedTopicSlugs = new Set(
    technologyTopicsForTrack({ name: trackName, aliases: [] }).map(
      (topic) => topic.slug,
    ),
  );

  return technologyTopicsForText(values).filter((topic) =>
    allowedTopicSlugs.has(topic.slug),
  );
}
