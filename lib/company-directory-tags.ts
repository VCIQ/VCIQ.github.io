export function companyDirectoryRelationTags(record: {
  relatedTracks: string[];
  relatedTopics: string[];
  relatedPeople: string[];
}) {
  return [
    ...new Set([
      ...record.relatedTracks,
      ...record.relatedTopics,
      ...record.relatedPeople,
    ]),
  ].slice(0, 4);
}
