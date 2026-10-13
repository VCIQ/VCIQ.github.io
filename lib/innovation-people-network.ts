import seed from "../config/innovation_people_network.json";
import roster from "../config/innovation_global_investors.json";
import evidence from "../config/innovation_investor_evidence.json";
import identities from "../config/innovation_investor_project_identities.json";

export type NetworkPerson = {
  id: string; name: string; aliases: string[]; kind: "investor" | "founder";
  institutionId: string | null; companySlug: string | null; companyName: string | null;
  personSlug: string | null; profileRole: string; topics: string[]; evidenceNames: string[];
  officialSource: { url: string; title: string; publishedAt: string | null; checkedAt: string };
  linkedin: { url: string; status: "candidate"; checkedAt: string;
    query: { firstName?: string; lastName?: string; company?: string } } | null;
};
export type PersonEvidence = {
  id: string; type: "viewpoint" | "portfolio-partner"; label: string;
  institutionId: string; institutionName: string; project: string | null;
  projectId: string | null; date: string; title: string; sourceUrl: string; caveat: string;
};
export type NetworkPersonView = NetworkPerson & {
  organization: string; relations: PersonEvidence[];
};
export const peopleNetworkReviewedAt = seed.reviewedAt;
export const peopleNetworkSeed = seed.people as NetworkPerson[];

export function safePublicUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password && (!u.port || u.port === "443") &&
      /\.[a-z]{2,}$/i.test(u.hostname) && !/\.(local|internal|localhost)$/i.test(u.hostname);
  } catch { return false; }
}

/** Retain only a LinkedIn profile URL. Search results never imply an employment or deal edge. */
export function normalizeLinkedInProfile(value: string): string | null {
  try {
    const u = new URL(value);
    if (!safePublicUrl(value) || !/^(?:[a-z]{2,3}\.)?linkedin\.com$/i.test(u.hostname) ||
        !/^\/in\/[^/]+\/?$/.test(u.pathname) || /%2f|%5c/i.test(u.pathname)) return null;
    return `https://www.linkedin.com${u.pathname.replace(/\/$/, "")}`;
  } catch { return null; }
}

export function validatePeopleNetwork(people: readonly NetworkPerson[] = peopleNetworkSeed): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();
  const profiles = new Set<string>();
  const names = new Set<string>();
  const dateOkay = (d: string) => /^\d{4}-\d{2}-\d{2}$/.test(d) && Number.isFinite(Date.parse(d));
  for (const person of people) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(person.id) || ids.has(person.id)) errors.push(`invalid person ID: ${person.id}`);
    ids.add(person.id);
    if (!person.name.trim() || !person.profileRole.trim() || !person.officialSource.title.trim() ||
        !safePublicUrl(person.officialSource.url) || !dateOkay(person.officialSource.checkedAt)) errors.push(`missing identity evidence: ${person.id}`);
    if (person.officialSource.publishedAt && !dateOkay(person.officialSource.publishedAt)) errors.push(`invalid source date: ${person.id}`);
    if (!["investor", "founder"].includes(person.kind)) errors.push(`unknown person kind: ${person.id}`);
    if (person.kind === "investor" && !roster.institutions.some(x => x.id === person.institutionId)) errors.push(`unknown institution: ${person.id}`);
    if (person.kind === "founder" && (!person.companyName || person.institutionId)) errors.push(`founder missing company: ${person.id}`);
    for (const slug of [person.personSlug, person.companySlug]) if (slug && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) errors.push(`invalid internal slug: ${person.id}`);
    for (const name of person.evidenceNames) {
      const key = `${person.institutionId}:${name}`;
      if (names.has(key)) errors.push(`ambiguous evidence identity: ${key}`);
      names.add(key);
      if (!evidence.records.some(r => r.institutionId === person.institutionId &&
          (r.speakers.some(s => s.name === name) || r.linkedPerson?.name === name))) errors.push(`unmapped evidence identity: ${person.id}:${name}`);
    }
    if (person.linkedin) {
      const url = normalizeLinkedInProfile(person.linkedin.url);
      if (!url || profiles.has(url)) errors.push(`invalid or duplicate LinkedIn profile: ${person.id}`);
      if (url) profiles.add(url);
      if (person.linkedin.status !== "candidate" || !dateOkay(person.linkedin.checkedAt) ||
          !(person.linkedin.query.firstName || person.linkedin.query.lastName)) errors.push(`unsupported LinkedIn assertion: ${person.id}`);
    }
  }
  return errors;
}

export function buildPeopleNetwork(people: readonly NetworkPerson[] = peopleNetworkSeed): NetworkPersonView[] {
  const errors = validatePeopleNetwork(people);
  if (errors.length) throw new Error(errors.join("; "));
  return people.map(person => {
    const institution = roster.institutions.find(x => x.id === person.institutionId);
    const relations: PersonEvidence[] = [];
    // Exact reviewed name + institution, never fuzzy matching or splitting a co-author string.
    for (const row of evidence.records.filter(r => r.institutionId === person.institutionId)) {
      const speaker = row.speakers.find(s => person.evidenceNames.includes(s.name));
      const partner = row.linkedPerson && person.evidenceNames.includes(row.linkedPerson.name);
      if (!speaker && !partner) continue;
      const project = identities.projects.find(p => p.observedNames.some(n => n === row.project));
      relations.push({id: row.id, type: speaker ? "viewpoint" : "portfolio-partner",
        label: speaker ? "公开观点" : "组合页关联人", institutionId: row.institutionId,
        institutionName: institution!.name, project: row.project, projectId: project?.id ?? null,
        date: row.date, title: row.title, sourceUrl: row.source.url,
        caveat: speaker?.projectResponsibility ?? "官网列示关联合伙人；不证明某轮领投、个人出资或交易签约责任。"});
    }
    return {...person, organization: institution?.name ?? person.companyName ?? "",
      relations: relations.sort((a,b) => b.date.localeCompare(a.date))};
  });
}

export function peopleForInstitution(id: string) {
  return buildPeopleNetwork().filter(person => person.institutionId === id);
}

/** A queue of exact, unsplit attributions still missing a reviewed person mapping. */
export function peopleNetworkCoverage() {
  const mapped = new Set(peopleNetworkSeed.flatMap(p => p.evidenceNames.map(n => `${p.institutionId}:${n}`)));
  const missing = new Map<string, {name: string; institutionId: string; sourceUrl: string}>();
  for (const r of evidence.records) for (const name of [
    ...r.speakers.map(s => s.name), ...(r.linkedPerson ? [r.linkedPerson.name] : []),
  ]) {
    const key = `${r.institutionId}:${name}`;
    if (!mapped.has(key)) missing.set(key, {name, institutionId:r.institutionId, sourceUrl:r.source.url});
  }
  return {mappedPeople: peopleNetworkSeed.length, pendingAttributions: [...missing.values()]};
}
