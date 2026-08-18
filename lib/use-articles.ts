"use client";

import { useCallback, useEffect, useState } from "react";
import {
  mergeRankedIntelligenceIntoArticlePayload,
  parseRankedIntelligenceProjection,
} from "@/lib/ranked-intelligence";
import type { RefreshAudit } from "@/lib/snapshot-freshness";

export type Region = "中国" | "美国" | "全球";
export type EventType =
  | "融资"
  | "产业投资"
  | "产品发布"
  | "技术突破"
  | "商业进展"
  | "公司动态"
  | "并购"
  | "财报"
  | "政策"
  | "监管文件"
  | "IPO"
  | "论文"
  | "人物观点";

export type IntelligenceSource = {
  name: string;
  url: string;
  level:
    | "官方披露"
    | "原始材料"
    | "监管文件"
    | "媒体报道"
    | "数据库记录"
    | "待交叉验证";
  platform?: string;
};

export type IntelligenceEvent = {
  id: string;
  title: string;
  summary: string;
  type: EventType;
  region: Region;
  sector: string;
  company: string;
  companySlug?: string;
  personSlug?: string;
  sourceId?: string;
  authors?: string[];
  institutions?: string[];
  publishedAt: string;
  importance: number;
  source: IntelligenceSource;
  curated?: boolean;
};

export type RelatedArticleSource = {
  name: string;
  url: string;
  level: string;
  platform: string;
  title: string;
  publishedAt: string;
};

export type LiveIntelligenceEvent = IntelligenceEvent & {
  qualityScore?: number;
  qualityStatus?: "高可信" | "可用" | "低可信";
  qualitySignals?: string[];
  relatedSources?: RelatedArticleSource[];
  duplicateCount?: number;
  eventClusterId?: string;
  wechatAccount?: string;
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  matchedTrackingTerms?: string[];
};

export type ArticleSourceStatus = {
  id: string;
  name: string;
  status: string;
  scanned: number;
  accepted: number;
  failed?: number;
  platform?: string;
  error?: string;
};

export type ArticleQualityGate = {
  passed: boolean;
  checks: Record<string, { actual: number; required: number; passed: boolean }>;
  invalidArticles?: { id: string; errors: string[] }[];
  trackingQuality?: {
    scoredUserArticles: number;
    acceptedUserArticles: number;
    rejectedUserArticles: number;
    clusteredDuplicates: number;
    minimumScore: number;
  };
};

export type ArticlePayload = {
  schemaVersion: number;
  generatedAt: string;
  articleCount: number;
  articles: LiveIntelligenceEvent[];
  sourceStatus?: ArticleSourceStatus[];
  qualityGate?: ArticleQualityGate;
  refreshAudit?: RefreshAudit;
};

const emptyPayload: ArticlePayload = {
  schemaVersion: 1,
  generatedAt: "",
  articleCount: 0,
  articles: [],
  sourceStatus: [],
};

const ARTICLE_CACHE_TTL_MS = 20 * 60_000;
const ARTICLE_REFRESH_INTERVAL_MS = 30 * 60_000;

let cachedPayload: ArticlePayload | null = null;
let cachedAt = 0;
let inFlight: Promise<ArticlePayload> | null = null;
const subscribers = new Set<(payload: ArticlePayload) => void>();

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/**
 * Browser reads only a shallow contract here. The production snapshot is
 * already validated article-by-article by the crawler, Pages build and public
 * artifact gates. Repeating the full Zod walk over ~2.4 MB on every page load
 * created a long synchronous task on the browser main thread.
 */
export function parseArticlePayload(value: unknown): ArticlePayload {
  if (!isRecord(value)) throw new Error("Public article data is not an object");
  if (typeof value.schemaVersion !== "number") {
    throw new Error("Public article data is missing schemaVersion");
  }
  if (typeof value.generatedAt !== "string") {
    throw new Error("Public article data is missing generatedAt");
  }
  if (!Array.isArray(value.articles)) {
    throw new Error("Public article data is missing articles");
  }

  const first = value.articles[0];
  if (
    first !== undefined &&
    (!isRecord(first) ||
      typeof first.id !== "string" ||
      typeof first.title !== "string" ||
      !isRecord(first.source) ||
      typeof first.source.url !== "string")
  ) {
    throw new Error("Public article data has an invalid article contract");
  }

  return value as unknown as ArticlePayload;
}

function publishArticlePayload(payload: ArticlePayload) {
  cachedPayload = payload;
  cachedAt = Date.now();
  for (const subscriber of subscribers) subscriber(payload);
}

async function fetchRankedIntelligenceProjectionFromNetwork(): Promise<unknown | null> {
  try {
    const response = await fetch("/data/ranked-intelligence.json", { cache: "default" });
    if (!response.ok) return null;
    const value = await response.json();
    parseRankedIntelligenceProjection(value);
    return value;
  } catch {
    // The homepage publication bridge is intentionally fail-open: the canonical
    // article snapshot must remain usable even when the optional projection is
    // missing, stale, or temporarily malformed.
    return null;
  }
}

async function fetchArticlesFromNetwork(): Promise<ArticlePayload> {
  const [response, rankedProjection] = await Promise.all([
    fetch("/data/articles.json", { cache: "default" }),
    fetchRankedIntelligenceProjectionFromNetwork(),
  ]);
  if (!response.ok) {
    throw new Error(`Public article data returned ${response.status}`);
  }
  const payload = parseArticlePayload(await response.json());
  return rankedProjection
    ? mergeRankedIntelligenceIntoArticlePayload(payload, rankedProjection)
    : payload;
}

async function loadArticles(force = false): Promise<ArticlePayload> {
  if (
    !force &&
    cachedPayload &&
    Date.now() - cachedAt < ARTICLE_CACHE_TTL_MS
  ) {
    return cachedPayload;
  }
  if (inFlight) return inFlight;

  inFlight = fetchArticlesFromNetwork()
    .then((payload) => {
      publishArticlePayload(payload);
      return payload;
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

function subscribeArticles(subscriber: (payload: ArticlePayload) => void): () => void {
  subscribers.add(subscriber);
  return () => {
    subscribers.delete(subscriber);
  };
}

export function useArticles(
  initialPayload: ArticlePayload = emptyPayload,
  options: { enabled?: boolean } = {},
) {
  // With build-time bootstrap data available, wait until the first real user
  // interaction before loading the complete multi-megabyte event archive.
  // Search no longer uses this hook; it consumes a compact event index instead.
  const [interactionEnabled, setInteractionEnabled] = useState(false);
  const [payload, setPayload] = useState<ArticlePayload>(() => cachedPayload ?? initialPayload);
  const [error, setError] = useState<Error | null>(null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (options.enabled !== undefined || interactionEnabled) return;
    const activate = () => setInteractionEnabled(true);
    window.addEventListener("pointerdown", activate, { once: true, passive: true });
    window.addEventListener("keydown", activate, { once: true });
    return () => {
      window.removeEventListener("pointerdown", activate);
      window.removeEventListener("keydown", activate);
    };
  }, [interactionEnabled, options.enabled]);

  const enabled = options.enabled ?? interactionEnabled;

  useEffect(() => {
    if (!enabled) return;
    return subscribeArticles((nextPayload) => {
      setPayload(nextPayload);
      setError(null);
    });
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    let active = true;

    const refresh = async () => {
      setIsFetching(true);
      try {
        const nextPayload = await loadArticles();
        if (!active) return;
        setPayload(nextPayload);
        setError(null);
      } catch (value) {
        if (!active) return;
        setError(value instanceof Error ? value : new Error(String(value)));
      } finally {
        if (active) setIsFetching(false);
      }
    };

    void refresh();
    const interval = window.setInterval(() => void refresh(), ARTICLE_REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [enabled]);

  const refetch = useCallback(async () => {
    setIsFetching(true);
    try {
      const nextPayload = await loadArticles(true);
      setPayload(nextPayload);
      setError(null);
      return nextPayload;
    } catch (value) {
      const nextError = value instanceof Error ? value : new Error(String(value));
      setError(nextError);
      throw nextError;
    } finally {
      setIsFetching(false);
    }
  }, []);

  const isLive = Boolean(enabled && cachedPayload && payload === cachedPayload);
  const hasData = payload.articles.length > 0 || Boolean(payload.generatedAt);

  return {
    data: payload,
    error,
    status: error ? "error" as const : hasData ? "success" as const : "pending" as const,
    fetchStatus: isFetching ? "fetching" as const : "idle" as const,
    isPending: !hasData && !error,
    isLoading: isFetching && !hasData,
    isFetching,
    isSuccess: !error && hasData,
    isError: Boolean(error),
    isPlaceholderData: !isLive,
    refetch,
    articles: payload.articles,
    generatedAt: payload.generatedAt,
    sourceStatus: payload.sourceStatus ?? [],
    qualityGate: payload.qualityGate,
    refreshAudit: payload.refreshAudit,
    isLive,
  };
}
