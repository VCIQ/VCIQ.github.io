import rawRegistry from "@/config/company_registry.json";
import type { Company } from "@/lib/catalog-data";

export type CompanyRegistryEntry = Company & {
  aliases: string[];
  registrySource: string;
  onboarding?: {
    candidateKey?: string;
    reviewedBy?: string;
    decidedAt?: string;
    publishedAt?: string;
    evidenceFingerprint?: string;
  };
};

type CompanyRegistryPayload = {
  schemaVersion?: number;
  generatedAt?: string;
  companies?: unknown[];
};

function text(value: unknown, limit = 1_200) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function unique(values: unknown, limit = 30) {
  if (!Array.isArray(values)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const item = text(value, 300);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function publicUrl(value: unknown) {
  const url = text(value, 2_000);
  return /^https?:\/\//iu.test(url) ? url : "";
}

function normalizeEntry(value: unknown): CompanyRegistryEntry | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const source = row.source && typeof row.source === "object"
    ? (row.source as Record<string, unknown>)
    : {};
  const slug = text(row.slug, 120).toLocaleLowerCase("en-US");
  const name = text(row.name, 240);
  const sourceUrl = publicUrl(source.url);
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(slug) || !name || !sourceUrl) {
    return null;
  }
  const status = row.status === "已上市" ? "已上市" : "运营中";
  const onboarding = row.onboarding && typeof row.onboarding === "object"
    ? (row.onboarding as Record<string, unknown>)
    : undefined;
  return {
    slug,
    name,
    englishName: text(row.englishName, 240) || undefined,
    region: text(row.region, 80) || "全球",
    sector: text(row.sector, 120) || "待分类",
    stage: text(row.stage, 80) || "待补充",
    status,
    founded: text(row.founded, 40) || undefined,
    headquarters: text(row.headquarters, 160) || undefined,
    summary: text(row.summary, 1_200),
    product: text(row.product, 1_200),
    source: {
      name: text(source.name, 240) || name,
      url: sourceUrl,
      level: "官方披露",
    },
    confidence: Math.max(0.5, Math.min(1, Number(row.confidence) || 0.9)),
    aliases: unique(row.aliases),
    registrySource: text(row.registrySource, 120) || "manual",
    onboarding: onboarding
      ? {
          candidateKey: text(onboarding.candidateKey, 160) || undefined,
          reviewedBy: text(onboarding.reviewedBy, 120) || undefined,
          decidedAt: text(onboarding.decidedAt, 80) || undefined,
          publishedAt: text(onboarding.publishedAt, 80) || undefined,
          evidenceFingerprint:
            text(onboarding.evidenceFingerprint, 10_000) || undefined,
        }
      : undefined,
  };
}

const payload = rawRegistry as CompanyRegistryPayload;

export const companyRegistryGeneratedAt = text(payload.generatedAt, 80);
export const companyRegistryEntries = (payload.companies ?? [])
  .map(normalizeEntry)
  .filter((entry): entry is CompanyRegistryEntry => entry !== null);

export const companies: Company[] = companyRegistryEntries.map((entry) => ({
  slug: entry.slug,
  name: entry.name,
  englishName: entry.englishName,
  region: entry.region,
  sector: entry.sector,
  stage: entry.stage,
  status: entry.status,
  founded: entry.founded,
  headquarters: entry.headquarters,
  summary: entry.summary,
  product: entry.product,
  source: entry.source,
  confidence: entry.confidence,
}));

export function companyRegistryEntry(slug: string) {
  return companyRegistryEntries.find((entry) => entry.slug === slug);
}
