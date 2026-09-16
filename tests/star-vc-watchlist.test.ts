import assert from "node:assert/strict";
import test from "node:test";

import {
  buildStarVcWatchlist,
  type StarVcWatchlist,
} from "../scripts/build-star-vc-watchlist";
import type { StarMarketInvestorRecord } from "../lib/star-market-investor-data";

function record({
  investorName,
  investorType = "其他机构股东",
  reviewStatus = "verified",
  company = "澜起科技",
  ticker = "688008",
  directoryType,
  rankingCategory,
}: {
  investorName: string;
  investorType?: string;
  reviewStatus?: "verified" | "needs_review" | "rejected";
  company?: string;
  ticker?: string;
  directoryType?: string;
  rankingCategory?: "早期投资" | "创业投资" | "私募股权" | "战略投资者/CVC";
}): StarMarketInvestorRecord {
  const directoryInstitution = directoryType || rankingCategory
    ? {
        name: investorName,
        region: "中国" as const,
        type: directoryType ?? "投资机构",
        stages: "全阶段",
        sectors: ["科技"],
        rankings: rankingCategory
          ? [
              {
                publisher: "清科" as const,
                year: 2025 as const,
                category: rankingCategory,
                title: "测试榜单",
                ordered: false,
                sourceId: "test-ranking",
                sourceUrl: "https://example.com/ranking",
              },
            ]
          : [],
      }
    : undefined;

  return {
    company: {
      slug: ticker,
      name: company,
      ticker,
      exchange: "上海证券交易所科创板",
      sector: "半导体",
      updatedAt: "2026-09-16T00:00:00Z",
      status: "ok",
      prospectus: {
        title: "首次公开发行股票并在科创板上市招股说明书",
        url: `https://static.cninfo.com.cn/${ticker}.PDF`,
        publishedAt: "2020-01-01",
        announcementId: ticker,
        pageCount: 100,
        textPageCount: 100,
        sha256: "abc",
        provider: "cninfo-prospectus",
      },
      institutionalInvestorCount: 1,
      naturalPersonContactsPublished: false,
      investors: [],
      errors: [],
    },
    investor: {
      id: `investor-${ticker}-${investorName}`,
      name: investorName,
      normalizedName: investorName.toLocaleLowerCase("zh-CN"),
      institutional: true,
      investorType,
      sourcePage: 88,
      sourceSection: "发行前股东",
      evidence: `${investorName} 10.0%`,
      contactStatus: "not-disclosed-in-prospectus",
      reviewStatus,
      reviewReasons: ["official-cninfo-prospectus"],
      preIpoOwnershipPct: 10,
    },
    directoryInstitution,
  } as StarMarketInvestorRecord;
}

function names(payload: StarVcWatchlist): string[] {
  return payload.institutions.map((institution) => institution.name);
}

test("watchlist admits only verified investment institutions", () => {
  const payload = buildStarVcWatchlist(
    [
      record({ investorName: "深创投集团", directoryType: "风险投资" }),
      record({ investorName: "珠海融英股权投资合伙企业（有限合伙）", investorType: "股权投资机构" }),
      record({ investorName: "Intel Capital Corporation" }),
      record({ investorName: "某科技制造有限公司" }),
      record({ investorName: "待审核创投基金", investorType: "股权投资机构", reviewStatus: "needs_review" }),
    ],
    "2026-09-16T00:00:00Z",
  );

  assert.deepEqual(names(payload), [
    "Intel Capital Corporation",
    "深创投集团",
    "珠海融英股权投资合伙企业（有限合伙）",
  ]);
  assert.equal(payload.stats.verifiedRelationshipCount, 4);
  assert.equal(payload.stats.trackedInstitutionCount, 3);
  assert.equal(payload.stats.highConfidenceCount, 2);
  assert.equal(payload.stats.mediumConfidenceCount, 1);
});

test("directory ranking evidence makes a verified shareholder high confidence", () => {
  const payload = buildStarVcWatchlist(
    [record({ investorName: "测试投资机构", rankingCategory: "创业投资" })],
    "2026-09-16T00:00:00Z",
  );
  assert.equal(payload.institutions[0]?.confidence, "high");
  assert.ok(
    payload.institutions[0]?.classificationReasons.includes(
      "directory-ranking:创业投资",
    ),
  );
});

test("same institution is deduplicated while preserving portfolio companies", () => {
  const payload = buildStarVcWatchlist(
    [
      record({ investorName: "Example Capital", ticker: "688001", company: "公司甲" }),
      record({ investorName: "Example Capital", ticker: "688002", company: "公司乙" }),
    ],
    "2026-09-16T00:00:00Z",
  );
  assert.equal(payload.institutions.length, 1);
  assert.deepEqual(
    payload.institutions[0]?.portfolioCompanies.map((company) => company.ticker),
    ["688001", "688002"],
  );
});

test("watchlist shards institution names instead of truncating one giant query", () => {
  const rows = Array.from({ length: 18 }, (_, index) =>
    record({
      investorName: `测试资本${String(index + 1).padStart(2, "0")}`,
      investorType: "股权投资机构",
      ticker: `688${String(index + 1).padStart(3, "0")}`,
    }),
  );
  const payload = buildStarVcWatchlist(rows, "2026-09-16T00:00:00Z");
  assert.equal(payload.queryShards.length, 3);
  assert.deepEqual(
    payload.queryShards.map((shard) => shard.institutionNames.length),
    [8, 8, 2],
  );
  assert.equal(
    payload.queryShards.flatMap((shard) => shard.institutionNames).length,
    payload.institutions.length,
  );
});
