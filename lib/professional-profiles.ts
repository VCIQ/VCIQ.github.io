import registry from "../config/people_professional_profiles.json";
import { normalizeLinkedInProfile, safePublicUrl } from "./public-profile-url";

export type ProfessionalProfileStatus = "matched" | "unresolved" | "no_result" | "needs_identity" | "search_error";
export type ProfessionalProfile = {
  personSlug: string; name: string; status: ProfessionalProfileStatus; checkedAt: string;
  linkedinUrl: string | null; identityContext: string | null; matchReason: string | null;
  sources: {url: string; title: string}[]; note: string;
  search: {provider: string; queries: {firstName?: string; lastName?: string; company?: string}[]; candidateCount: number} | null;
};
export const professionalProfileLabels: Record<ProfessionalProfileStatus | "not_reviewed", string> = {
  matched: "LinkedIn 身份已交叉核对",
  unresolved: "同名候选待核验",
  no_result: "本轮未找到匹配档案",
  needs_identity: "人物名称待修正",
  search_error: "检索待重试",
  not_reviewed: "职业档案待核验",
};
export const professionalProfilesReviewedAt = registry.reviewedAt;
export const professionalProfiles = registry.profiles as ProfessionalProfile[];

export function validateProfessionalProfiles(rows: readonly ProfessionalProfile[] = professionalProfiles): string[] {
  const errors: string[] = [];
  const slugs = new Set<string>();
  const urls = new Set<string>();
  for (const row of rows) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(row.personSlug) || slugs.has(row.personSlug))
      errors.push(`invalid or duplicate slug: ${row.personSlug}`);
    slugs.add(row.personSlug);
    if (!(Object.hasOwn(professionalProfileLabels, row.status)) || row.status === ("not_reviewed" as string))
      errors.push(`invalid status: ${row.personSlug}`);
    if (!row.name.trim() || !row.note.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(row.checkedAt) || !Number.isFinite(Date.parse(row.checkedAt)))
      errors.push(`incomplete review: ${row.personSlug}`);
    if (row.sources.some(s => !s.title.trim() || !safePublicUrl(s.url)))
      errors.push(`unsafe source: ${row.personSlug}`);
    if (row.status === "matched") {
      const url = row.linkedinUrl && normalizeLinkedInProfile(row.linkedinUrl);
      const independent = row.sources.some(s => safePublicUrl(s.url) && !/(^|\.)linkedin\.com$/i.test(new URL(s.url).hostname));
      const profileSource = row.sources.some(s => normalizeLinkedInProfile(s.url) === url);
      if (!url || url !== row.linkedinUrl || urls.has(url) || !row.matchReason?.trim() ||
          !row.identityContext?.trim() || !independent || !profileSource)
        errors.push(`unsupported identity binding: ${row.personSlug}`);
      if (url) urls.add(url);
    } else if (row.linkedinUrl || row.matchReason || row.identityContext) {
      errors.push(`unreviewed binding: ${row.personSlug}`);
    }
    if (row.search && (!Number.isInteger(row.search.candidateCount) || row.search.candidateCount < 0 ||
        !row.search.queries.length || row.search.queries.some(q => !(q.firstName || q.lastName))))
      errors.push(`invalid search record: ${row.personSlug}`);
  }
  return errors;
}
const errors = validateProfessionalProfiles();
if (errors.length) throw new Error(errors.join("; "));
const bySlug = new Map(professionalProfiles.map(row => [row.personSlug, row]));
export function getProfessionalProfile(slug: string) { return bySlug.get(slug); }
export function professionalProfileCoverage(slugs: readonly string[]) {
  const counts = {matched: 0, unresolved: 0, no_result: 0, needs_identity: 0, search_error: 0, not_reviewed: 0};
  for (const slug of new Set(slugs)) counts[getProfessionalProfile(slug)?.status ?? "not_reviewed"]++;
  return counts;
}
