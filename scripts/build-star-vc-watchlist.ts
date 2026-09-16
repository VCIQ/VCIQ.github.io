import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  starMarketInvestorAllRecords,
  starMarketInvestorGeneratedAt,
  type StarMarketInvestorRecord,
} from "../lib/star-market-investor-data";

const ROOT = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const OUTPUT_PATH = path.join(ROOT, "config/star_vc_watchlist.json");
const QUERY_SHARD_SIZE = 8;

const VC_RANKING_CATEGORIES = new Set([
  "早期投资",
  "创业投资",
  "私募股权",
  "战略投资者/CVC",
]);
const DIRECTORY_TYPE_RE = /风险投资|创业投资|私募股权|产业资本|\bCVC\b|venture|private\s+equity/iu;
const INVESTOR_TYPE_RE = /股权投资机构|创业投资机构|风险投资机构|私募股权|产业投资机构|战略投资机构|创投机构/iu;
const INVESTMENT_NAME_RE = /资本|基金|创投|创业投资|股权投资|投资基金|投资合伙|资产管理|投资控股|证券投资|\binvestments?\b|\bcapital\b|\bventures?\b|\bpartners?\b|\bfunds?\b/iu;

export type StarVcPortfolioCompany = {
  slug: string;
  name: string;
  ticker: string;
  sector: string;
  preIpoOwnershipPct?: number;
  prospectusUrl: string;
  sourcePage: number;
  evidence: string;
};

export type StarVcInstitution = {
  name: string;
  normalizedName: string;
  directoryName?: string;
  directoryType?: string;
  confidence: "high" | "medium";
  classificationReasons: string[];
  portfolioCompanies: StarVcPortfolioCompany[];
};

export type StarVcWatchlist = {
  schemaVersion: 1;
  generatedAt: string;
  source: "star-market-verified-investors";
  methodology: {
    relationshipRule: string;
    classificationRule: string;
    queryShardSize: number;
  };
  stats: {
    verifiedRelationshipCount: number;
    trackedInstitutionCount: number;
    highConfidenceCount: number;
    mediumConfidenceCount: number;
    queryShardCount: number;
  };
  institutions: StarVcInstitution[];
  queryShards: { id: string; institutionNames: string[] }[];
};

function normalize(value: unknown): string {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "")
    .trim();
}

function classificationReasons(record: StarMarketInvestorRecord): string[] {
  const reasons: string[] = [];
  const directory = record.directoryInstitution;

  if (INVESTOR_TYPE_RE.test(record.investor.investorType ?? "")) {
    reasons.push(`prospectus-type:${record.investor.investorType}`);
  }
  if (directory?.type && DIRECTORY_TYPE_RE.test(directory.type)) {
    reasons.push(`directory-type:${directory.type}`);
  }
  for (const ranking of directory?.rankings ?? []) {
    if (VC_RANKING_CATEGORIES.has(ranking.category)) {
      reasons.push(`directory-ranking:${ranking.category}`);
    }
  }
  if (!reasons.length && INVESTMENT_NAME_RE.test(record.investor.name)) {
    reasons.push("verified-investment-name");
  }
  return [...new Set(reasons)].sort();
}

function recordConfidence(reasons: string[]): "high" | "medium" {
  return reasons.some((reason) => !reason.startsWith("verified-investment-name"))
    ? "high"
    : "medium";
}

function portfolioCompany(record: StarMarketInvestorRecord): StarVcPortfolioCompany {
  return {
    slug: record.company.slug,
    name: record.company.name,
    ticker: record.company.ticker,
    sector: record.company.sector,
    preIpoOwnershipPct: record.investor.preIpoOwnershipPct,
    prospectusUrl: record.company.prospectus.url,
    sourcePage: record.investor.sourcePage,
    evidence: record.investor.evidence,
  };
}

export function buildStarVcWatchlist(
  records: StarMarketInvestorRecord[],
  generatedAt: string,
): StarVcWatchlist {
  const verified = records.filter(
    (record) => record.investor.reviewStatus === "verified",
  );
  const byInstitution = new Map<string, StarVcInstitution>();

  for (const record of verified) {
    const reasons = classificationReasons(record);
    if (!reasons.length) continue;

    const canonicalName = record.directoryInstitution?.name || record.investor.name;
    const key = normalize(canonicalName || record.investor.normalizedName);
    if (!key) continue;

    const confidence = recordConfidence(reasons);
    const existing = byInstitution.get(key);
    if (!existing) {
      byInstitution.set(key, {
        name: canonicalName,
        normalizedName: key,
        directoryName: record.directoryInstitution?.name,
        directoryType: record.directoryInstitution?.type,
        confidence,
        classificationReasons: reasons,
        portfolioCompanies: [portfolioCompany(record)],
      });
      continue;
    }

    existing.classificationReasons = [
      ...new Set([...existing.classificationReasons, ...reasons]),
    ].sort();
    if (confidence === "high") existing.confidence = "high";
    if (!existing.directoryName && record.directoryInstitution?.name) {
      existing.directoryName = record.directoryInstitution.name;
      existing.directoryType = record.directoryInstitution.type;
      existing.name = record.directoryInstitution.name;
    }
    const company = portfolioCompany(record);
    const current = existing.portfolioCompanies.find(
      (item) => item.slug === company.slug,
    );
    if (!current) existing.portfolioCompanies.push(company);
  }

  const institutions = [...byInstitution.values()]
    .map((institution) => ({
      ...institution,
      portfolioCompanies: [...institution.portfolioCompanies].sort(
        (left, right) =>
          left.ticker.localeCompare(right.ticker) ||
          left.name.localeCompare(right.name, "zh-CN"),
      ),
    }))
    .sort(
      (left, right) =>
        Number(right.confidence === "high") - Number(left.confidence === "high") ||
        right.portfolioCompanies.length - left.portfolioCompanies.length ||
        left.name.localeCompare(right.name, "zh-CN"),
    );

  const queryShards: { id: string; institutionNames: string[] }[] = [];
  for (let offset = 0; offset < institutions.length; offset += QUERY_SHARD_SIZE) {
    const index = queryShards.length + 1;
    queryShards.push({
      id: `star-vc-${String(index).padStart(3, "0")}`,
      institutionNames: institutions
        .slice(offset, offset + QUERY_SHARD_SIZE)
        .map((institution) => institution.name),
    });
  }

  return {
    schemaVersion: 1,
    generatedAt,
    source: "star-market-verified-investors",
    methodology: {
      relationshipRule:
        "Only reviewStatus=verified institutional shareholder records from official STAR Market prospectuses are eligible.",
      classificationRule:
        "Track explicit VC/PE/CVC directory classifications or prospectus investor types; otherwise require a verified investment-institution name marker.",
      queryShardSize: QUERY_SHARD_SIZE,
    },
    stats: {
      verifiedRelationshipCount: verified.length,
      trackedInstitutionCount: institutions.length,
      highConfidenceCount: institutions.filter(
        (institution) => institution.confidence === "high",
      ).length,
      mediumConfidenceCount: institutions.filter(
        (institution) => institution.confidence === "medium",
      ).length,
      queryShardCount: queryShards.length,
    },
    institutions,
    queryShards,
  };
}

export function writeStarVcWatchlist(
  payload: StarVcWatchlist,
  outputPath = OUTPUT_PATH,
): void {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function run(): void {
  const payload = buildStarVcWatchlist(
    starMarketInvestorAllRecords,
    starMarketInvestorGeneratedAt,
  );
  writeStarVcWatchlist(payload);
  process.stdout.write(
    `${JSON.stringify({
      generatedAt: payload.generatedAt,
      verifiedRelationships: payload.stats.verifiedRelationshipCount,
      trackedInstitutions: payload.stats.trackedInstitutionCount,
      highConfidence: payload.stats.highConfidenceCount,
      mediumConfidence: payload.stats.mediumConfidenceCount,
      queryShards: payload.stats.queryShardCount,
    })}\n`,
  );
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  run();
}
