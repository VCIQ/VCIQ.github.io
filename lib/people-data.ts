import generatedPayload from "@/public/data/people.json";
import { people as curatedPeople, type Person } from "@/lib/catalog-data";
import { validatePersonIdentity } from "@/lib/person-identity-validation";

export type PersonMaterial = Person["materials"][number];

export type ResearchPerson = Person & {
  aliases: string[];
  handles: string[];
  sectors: string[];
  background: string;
  organizations: string[];
  products: string[];
  works: string[];
  books: string[];
  speeches: PersonMaterial[];
  sources: string[];
  status: "complete" | "partial" | "pending";
  updatedAt: string;
  tracked: boolean;
};

type GeneratedPerson = Omit<ResearchPerson, "tracked">;

type GeneratedPayload = {
  schemaVersion: number;
  generatedAt: string;
  personCount: number;
  excludedOrganizationAccounts?: string[];
  people: GeneratedPerson[];
};

const payload = generatedPayload as GeneratedPayload;

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = value.trim().toLocaleLowerCase("zh-CN");
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function uniqueMaterials(values: PersonMaterial[]): PersonMaterial[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    // Key on url + title: distinct curated materials may share a landing
    // page (e.g. a publisher's letters index), and dropping one would also
    // shift the evidenceIndex references authored against the catalog order.
    const url = value.url.trim().toLocaleLowerCase("en-US");
    const title = value.title.trim().toLocaleLowerCase("zh-CN");
    const key = `${url}|${title}`;
    if (key === "|" || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function deriveMaterialLists(person: ResearchPerson): ResearchPerson {
  const materials = uniqueMaterials(person.materials);
  const sourcedWorks = materials
    .filter((item) => ["authored_work", "research_paper"].includes(item.type))
    .map((item) => item.title);
  const sourcedBooks = materials
    .filter((item) => item.type === "authored_work" && /book|almanack|memoir|著作|传记|书/i.test(item.title))
    .map((item) => item.title);
  const speeches = uniqueMaterials([
    ...person.speeches,
    ...materials.filter((item) => ["speech", "interview", "qa"].includes(item.type)),
  ]);
  return {
    ...person,
    materials,
    works: uniqueStrings([...person.works, ...sourcedWorks]),
    books: uniqueStrings([...person.books, ...sourcedBooks]),
    speeches,
  };
}

function fromCurated(person: Person): ResearchPerson {
  return deriveMaterialLists({
    ...person,
    aliases: uniqueStrings([person.name, person.englishName]),
    handles: [],
    sectors: [],
    background: person.summary,
    organizations: [],
    products: [],
    works: [],
    books: [],
    speeches: [],
    sources: uniqueStrings(person.materials.map((item) => item.url)),
    status: person.materials.length >= 4 ? "complete" : "partial",
    updatedAt: "",
    tracked: false,
  });
}

function mergePerson(curated: ResearchPerson | undefined, generated: GeneratedPerson): ResearchPerson {
  if (!curated) return deriveMaterialLists({ ...generated, tracked: true });
  const materials = uniqueMaterials([...generated.materials, ...curated.materials]);
  return deriveMaterialLists({
    ...curated,
    ...generated,
    summary: generated.summary || curated.summary,
    background: generated.background || curated.background || curated.summary,
    concepts: uniqueStrings([...generated.concepts, ...curated.concepts]),
    aliases: uniqueStrings([...generated.aliases, ...curated.aliases]),
    handles: uniqueStrings([...generated.handles, ...curated.handles]),
    sectors: uniqueStrings([...generated.sectors, ...curated.sectors]),
    organizations: uniqueStrings([...generated.organizations, ...curated.organizations]),
    products: uniqueStrings([...generated.products, ...curated.products]),
    works: uniqueStrings([...generated.works, ...curated.works]),
    books: uniqueStrings([...generated.books, ...curated.books]),
    materials,
    speeches: uniqueMaterials([...generated.speeches, ...curated.speeches]),
    sources: uniqueStrings([...generated.sources, ...curated.sources]),
    status: generated.status === "complete" || curated.status === "complete" ? "complete" : generated.status,
    tracked: true,
  });
}

const generatedValidation = payload.people.map((person) => ({
  person,
  validation: validatePersonIdentity(person),
}));
const acceptedGeneratedPeople = generatedValidation
  .filter(({ validation }) => validation.valid)
  .map(({ person }) => person);

export const rejectedGeneratedPeople = generatedValidation
  .filter(({ validation }) => !validation.valid)
  .map(({ person, validation }) => ({
    slug: person.slug,
    name: person.name,
    reason: validation.reason ?? "identity-validation-failed",
  }));
export const rejectedGeneratedPeopleCount = rejectedGeneratedPeople.length;

const bySlug = new Map(curatedPeople.map((person) => [person.slug, fromCurated(person)]));
for (const generated of acceptedGeneratedPeople) {
  bySlug.set(generated.slug, mergePerson(bySlug.get(generated.slug), generated));
}

export const researchPeople: ResearchPerson[] = [...bySlug.values()].sort((left, right) => {
  if (left.tracked !== right.tracked) return left.tracked ? -1 : 1;
  const leftSector = left.sectors[0] ?? "其他";
  const rightSector = right.sectors[0] ?? "其他";
  return leftSector.localeCompare(rightSector, "zh-CN") || left.englishName.localeCompare(right.englishName, "en");
});

export const peopleGeneratedAt = payload.generatedAt;
export const excludedPersonAccounts = payload.excludedOrganizationAccounts ?? [];
