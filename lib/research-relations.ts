import { companies, type Company } from "@/lib/catalog-data";
import { companyRegistryEntries } from "@/lib/company-registry";
import { researchPeople } from "@/lib/people-data";
import { technologyTopicsForText } from "@/lib/technology-topic-matching";
import {
  technologyTopicDefinitions,
  technologyTopicsForTrack,
  type TechnologyTopicDefinition,
} from "@/lib/technology-topics";
import {
  getTrackedSector,
  trackedSectors,
  type TrackedSector,
} from "@/lib/tracked-sectors";
import { getCompanyVentureProfile } from "@/lib/venture-profile-data";

export type ResearchRelationLink = {
  slug: string;
  name: string;
  href: string;
  meta?: string;
};

export type CompanyResearchRelations = {
  tracks: ResearchRelationLink[];
  topics: ResearchRelationLink[];
  people: ResearchRelationLink[];
};

export type PersonResearchRelations = {
  tracks: ResearchRelationLink[];
  topics: ResearchRelationLink[];
  companies: ResearchRelationLink[];
};

export type TrackResearchRelations = {
  topics: ResearchRelationLink[];
  people: ResearchRelationLink[];
  companies: ResearchRelationLink[];
};

function normalizeIdentity(value: string) {
  return value
    .toLocaleLowerCase("zh-CN")
    .replace(/&/gu, "and")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "")
    .replace(
      /(?:股份有限公司|有限责任公司|有限公司|集团有限公司|集团|公司|incorporated|corporation|corp|inc|limited|ltd|llc|company|co)$/u,
      "",
    );
}

function identityKeys(values: Array<string | undefined>) {
  const keys = new Set<string>();
  for (const value of values) {
    if (!value) continue;
    const exact = value
      .toLocaleLowerCase("zh-CN")
      .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
    const normalized = normalizeIdentity(value);
    if (exact) keys.add(exact);
    if (normalized) keys.add(normalized);
  }
  return keys;
}

function intersects(left: Set<string>, right: Set<string>) {
  for (const value of left) {
    if (right.has(value)) return true;
  }
  return false;
}

function uniqueLinks(values: ResearchRelationLink[], limit = 12) {
  const result: ResearchRelationLink[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const key = `${value.href}|${value.name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(value);
    if (result.length >= limit) break;
  }
  return result;
}

function topicLink(topic: TechnologyTopicDefinition): ResearchRelationLink {
  return {
    slug: topic.slug,
    name: topic.name,
    href: `/technologies/#topic-${topic.slug}`,
    meta: topic.alertQuery,
  };
}

function trackLink(track: TrackedSector): ResearchRelationLink {
  return {
    slug: track.slug,
    name: track.name,
    href: `/technologies/tracks/${track.slug}`,
    meta: `${track.events} 项事件 · HeatScore ${track.heat}`,
  };
}

const companyAliasesBySlug = new Map(
  companyRegistryEntries.map((entry) => [
    entry.slug,
    identityKeys([
      entry.name,
      entry.englishName,
      ...entry.aliases,
    ]),
  ]),
);

function companyKeys(slug: string) {
  const company = companies.find((item) => item.slug === slug);
  return companyAliasesBySlug.get(slug) ?? identityKeys([
    company?.name,
    company?.englishName,
  ]);
}

function companyForOrganization(organization: string) {
  const organizationKeys = identityKeys([organization]);
  if (!organizationKeys.size) return undefined;
  return companies.find((company) =>
    intersects(organizationKeys, companyKeys(company.slug)),
  );
}

function tracksForSectorNames(values: string[]) {
  const keys = identityKeys(values);
  return trackedSectors.filter((track) =>
    intersects(keys, identityKeys([track.name, ...track.aliases])),
  );
}

function peopleForCompany(slug: string) {
  const keys = companyKeys(slug);
  return researchPeople
    .filter((person) => person.organizations.some((organization) =>
      intersects(identityKeys([organization]), keys),
    ))
    .map((person) => ({
      slug: person.slug,
      name: person.name,
      href: `/people/${person.slug}`,
      meta: person.role,
    }));
}

function companyTechnologyTopics(slug: string) {
  const company = companies.find((item) => item.slug === slug);
  if (!company) return [];
  const venture = getCompanyVentureProfile(slug);
  return technologyTopicsForText([
    company.name,
    company.englishName,
    company.summary,
    company.product,
    company.sector,
    venture?.background,
    venture?.projectBackground?.problemSolved,
    venture?.projectBackground?.marketOpportunity,
    venture?.technology,
    venture?.researchTechnology,
    ...(venture?.products ?? []),
    ...(venture?.technologyProducts ?? []).flatMap((product) => [
      product.name,
      product.category,
      product.description,
      ...(product.technicalHighlights ?? []),
    ]),
  ]).slice(0, 8);
}

export function getCompanyResearchRelations(slug: string): CompanyResearchRelations {
  const company = companies.find((item) => item.slug === slug);
  if (!company) return { tracks: [], topics: [], people: [] };
  const people = peopleForCompany(slug);
  const tracks = tracksForSectorNames([company.sector]);
  return {
    tracks: uniqueLinks(tracks.map(trackLink), 4),
    topics: uniqueLinks(companyTechnologyTopics(slug).map(topicLink), 6),
    people: uniqueLinks(people, 8),
  };
}

export function getPersonResearchRelations(slug: string): PersonResearchRelations {
  const person = researchPeople.find((item) => item.slug === slug);
  if (!person) return { tracks: [], topics: [], companies: [] };
  const relatedCompanies = uniqueLinks(
    person.organizations
      .map(companyForOrganization)
      .filter((company): company is Company => Boolean(company))
      .map((company) => ({
        slug: company.slug,
        name: company.name,
        href: `/companies/${company.slug}`,
        meta: `${company.sector} · ${company.stage}`,
      })),
    10,
  );
  const relatedCompanySectors = relatedCompanies
    .map((relation) => companies.find((company) => company.slug === relation.slug)?.sector)
    .filter((value): value is string => Boolean(value));
  const tracks = tracksForSectorNames([...person.sectors, ...relatedCompanySectors]);
  const topics = technologyTopicsForText([
    person.name,
    person.englishName,
    person.summary,
    person.background,
    person.role,
    ...person.sectors,
    ...person.concepts,
    ...person.products,
    ...person.works,
  ]);
  return {
    tracks: uniqueLinks(tracks.map(trackLink), 6),
    topics: uniqueLinks(topics.map(topicLink), 8),
    companies: relatedCompanies,
  };
}

export function getTrackResearchRelations(slug: string): TrackResearchRelations {
  const track = getTrackedSector(slug);
  if (!track) return { topics: [], people: [], companies: [] };
  const trackKeys = identityKeys([track.name, ...track.aliases]);
  const relatedCompanies = companies
    .filter((company) => intersects(identityKeys([company.sector]), trackKeys))
    .map((company) => ({
      slug: company.slug,
      name: company.name,
      href: `/companies/${company.slug}`,
      meta: `${company.region} · ${company.stage}`,
    }));
  const companySlugs = new Set(relatedCompanies.map((company) => company.slug));
  const people = researchPeople
    .filter((person) => {
      if (intersects(identityKeys(person.sectors), trackKeys)) return true;
      return person.organizations.some((organization) => {
        const company = companyForOrganization(organization);
        return company ? companySlugs.has(company.slug) : false;
      });
    })
    .map((person) => ({
      slug: person.slug,
      name: person.name,
      href: `/people/${person.slug}`,
      meta: person.role,
    }));
  return {
    topics: uniqueLinks(technologyTopicsForTrack(track).map(topicLink), 10),
    people: uniqueLinks(people, 10),
    companies: uniqueLinks(relatedCompanies, 14),
  };
}

export const researchSynergySummary = {
  trackCount: trackedSectors.length,
  topicCount: technologyTopicDefinitions.length,
  peopleCount: researchPeople.length,
  companyCount: companies.length,
  companyPersonEdges: companies.reduce(
    (sum, company) => sum + peopleForCompany(company.slug).length,
    0,
  ),
};
