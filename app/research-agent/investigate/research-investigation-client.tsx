"use client";

import {
  ArrowLeft,
  Bot,
  Check,
  Clipboard,
  ExternalLink,
  FileSearch,
  Link2,
  Radar,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useFavorites } from "@/components/use-favorites";
import { useHomepagePreferences } from "@/components/use-homepage-preferences";
import {
  buildHomepageFavoriteAffinityProfile,
  homepageFavoriteId,
  isHomepageSectorFollowed,
} from "@/lib/homepage-recommendation";
import {
  mergeRankedIntelligenceIntoArticlePayload,
  parseRankedIntelligenceProjection,
} from "@/lib/ranked-intelligence";
import {
  buildResearchContextUrl,
  buildResearchWorkspaceLaunchUrl,
  buildResearchWorkspacePrompt,
  type ResearchWorkspaceHandoff,
} from "@/lib/research-workspace-handoff";
import {
  parseArticlePayload,
  type ArticlePayload,
  type LiveIntelligenceEvent,
} from "@/lib/use-articles";
import styles from "./research-investigation.module.css";

const researchWorkspaceUrl = process.env.NEXT_PUBLIC_QM_WORKSPACE_URL?.trim() || "";

type LoadState = "loading" | "ready" | "missing" | "error";
type TerminalLoadState = Exclude<LoadState, "loading">;

type LoadResult = {
  eventId: string;
  state: TerminalLoadState;
  item: LiveIntelligenceEvent | null;
};

type CopyState = "idle" | "copied" | "failed";

function unique(values: Array<string | undefined>) {
  return [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])];
}

async function copyText(text: string) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {}

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  } catch {
    return false;
  }
}

async function loadResearchEvent(eventId: string) {
  const [articleResponse, rankedValue] = await Promise.all([
    fetch("/data/articles.json", { cache: "default" }),
    fetch("/data/ranked-intelligence.json", { cache: "default" })
      .then(async (response) => (response.ok ? response.json() : null))
      .catch(() => null),
  ]);

  if (!articleResponse.ok) {
    throw new Error(`articles.json returned ${articleResponse.status}`);
  }

  const payload = parseArticlePayload(await articleResponse.json());
  let merged: ArticlePayload = payload;
  if (rankedValue) {
    try {
      parseRankedIntelligenceProjection(rankedValue);
      merged = mergeRankedIntelligenceIntoArticlePayload(payload, rankedValue);
    } catch {
      // The canonical article snapshot is still sufficient for most handoffs.
    }
  }
  return merged.articles.find((candidate) => candidate.id === eventId) ?? null;
}

function relatedSourceLabel(item: NonNullable<LiveIntelligenceEvent["relatedSources"]>[number]) {
  return item.title?.trim() || item.name?.trim() || item.url;
}

export default function ResearchInvestigationClient() {
  const searchParams = useSearchParams();
  const eventId = searchParams.get("event")?.trim() || "";
  const favorites = useFavorites();
  const preferences = useHomepagePreferences();
  const favoriteProfile = useMemo(
    () => buildHomepageFavoriteAffinityProfile(favorites),
    [favorites],
  );
  const [result, setResult] = useState<LoadResult | null>(null);
  const [copyState, setCopyState] = useState<CopyState>("idle");

  useEffect(() => {
    if (!eventId) return;

    let cancelled = false;
    void loadResearchEvent(eventId)
      .then((nextItem) => {
        if (cancelled) return;
        setResult({
          eventId,
          state: nextItem ? "ready" : "missing",
          item: nextItem,
        });
      })
      .catch(() => {
        if (!cancelled) {
          setResult({ eventId, state: "error", item: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  const currentResult = result?.eventId === eventId ? result : null;
  const state: LoadState = !eventId
    ? "missing"
    : currentResult?.state ?? "loading";
  const item = currentResult?.item ?? null;

  const handoff = useMemo<ResearchWorkspaceHandoff | null>(() => {
    if (!item) return null;
    const savedForLater = favoriteProfile.favoriteIds.has(homepageFavoriteId(item));
    return {
      eventId: item.id,
      title: item.title,
      url: item.source.url,
      summary: item.summary,
      sector: item.sector,
      company: item.company,
      people: unique([...(item.mentionedPeople ?? []), ...(item.authors ?? [])]),
      companies: unique(item.mentionedCompanies ?? []),
      relatedSources: (item.relatedSources ?? []).map((source) => ({
        name: source.name,
        url: source.url,
        level: source.level,
        title: source.title,
        publishedAt: source.publishedAt,
      })),
      importance: item.importance,
      publishedAt: item.publishedAt,
      sourceName: item.source.name,
      sourceLevel: item.source.level,
      matchedTrackingTerms: item.matchedTrackingTerms,
      curated: item.curated,
      sectorFollowed: isHomepageSectorFollowed(item, preferences),
      savedForLater,
    };
  }, [favoriteProfile.favoriteIds, item, preferences]);

  const researchPrompt = useMemo(
    () => (handoff ? buildResearchWorkspacePrompt(handoff) : ""),
    [handoff],
  );
  const contextUrl = eventId ? buildResearchContextUrl(eventId) : "";
  const workspaceLaunchUrl = eventId
    ? buildResearchWorkspaceLaunchUrl(researchWorkspaceUrl, eventId, contextUrl)
    : "";

  async function copyResearchPrompt() {
    const copied = await copyText(researchPrompt);
    setCopyState(copied ? "copied" : "failed");
    window.setTimeout(() => setCopyState("idle"), 2200);
  }

  function openWorkspace() {
    if (!workspaceLaunchUrl || !researchPrompt) return;
    void copyResearchPrompt();
    window.open(workspaceLaunchUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <main className={`page-shell subpage ${styles.page}`}>
      <header className={styles.hero}>
        <Link href="/" className={styles.backLink}>
          <ArrowLeft size={14} aria-hidden="true" />
          返回今日推荐
        </Link>
        <p className="eyebrow">CONTEXTUAL RESEARCH HANDOFF</p>
        <h1>深研此条</h1>
        <p>
          先把当前情报整理成可复核的研究上下文，再移交 Research Workspace。这里不会把摘要或媒体措辞自动升级为事实。
        </p>
      </header>

      {state === "loading" ? (
        <section className={styles.statePanel} role="status">
          <FileSearch size={20} aria-hidden="true" />
          <div>
            <strong>正在读取当前情报与关联来源</strong>
            <p>仅在你主动进入深研时加载完整公开情报快照。</p>
          </div>
        </section>
      ) : null}

      {state === "missing" ? (
        <section className={styles.statePanel}>
          <FileSearch size={20} aria-hidden="true" />
          <div>
            <strong>{eventId ? "没有找到这条情报" : "缺少事件参数"}</strong>
            <p>请从首页某一条具体情报的“深研此条”入口进入；数据刷新后极少数旧事件 ID 也可能失效。</p>
          </div>
        </section>
      ) : null}

      {state === "error" ? (
        <section className={styles.statePanel}>
          <FileSearch size={20} aria-hidden="true" />
          <div>
            <strong>暂时无法读取公开情报快照</strong>
            <p>可以返回首页稍后重试；本页不会在加载失败时伪造研究上下文。</p>
          </div>
        </section>
      ) : null}

      {state === "ready" && item && handoff ? (
        <>
          <section className={styles.eventCard} aria-labelledby="investigation-title">
            <div className={styles.tagRow}>
              <span>{item.type}</span>
              <span>{item.region}</span>
              <span>{item.sector}</span>
              <span>重要度 {item.importance}</span>
            </div>
            <h2 id="investigation-title">{item.title}</h2>
            <p className={styles.summary}>{item.summary}</p>
            <div className={styles.sourceRow}>
              <a href={item.source.url} target="_blank" rel="noreferrer">
                {item.source.name} · {item.source.level}
                <ExternalLink size={13} aria-hidden="true" />
              </a>
              <time dateTime={item.publishedAt}>{item.publishedAt}</time>
            </div>
          </section>

          <section className={styles.contextGrid} aria-label="研究上下文">
            <article>
              <header><Radar size={16} aria-hidden="true" />追踪状态</header>
              <p>
                {handoff.sectorFollowed ? `已关注「${item.sector}」赛道` : `尚未显式关注「${item.sector}」赛道`}
              </p>
              <p>{handoff.savedForLater ? "已加入稍后读" : "未加入稍后读"}</p>
              <p>
                {item.matchedTrackingTerms?.length
                  ? `命中追踪词：${item.matchedTrackingTerms.join("、")}`
                  : "暂无命中追踪词"}
              </p>
            </article>
            <article>
              <header><Link2 size={16} aria-hidden="true" />关联对象</header>
              <p>公司：{unique([item.company, ...(item.mentionedCompanies ?? [])]).join("、") || "未明确"}</p>
              <p>人物：{unique([...(item.mentionedPeople ?? []), ...(item.authors ?? [])]).join("、") || "未明确"}</p>
              <p>事件 ID：{item.id}</p>
            </article>
            <article>
              <header><ShieldCheck size={16} aria-hidden="true" />证据入口</header>
              <p>主来源 1 个</p>
              <p>关联来源 {item.relatedSources?.length ?? 0} 个</p>
              <p>{item.qualityStatus ? `质量状态：${item.qualityStatus}` : "质量状态未标记"}</p>
            </article>
          </section>

          <section className={styles.sourcesSection}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">EVIDENCE STARTING POINTS</p>
                <h2>关联来源</h2>
              </div>
              <span>深研时仍应主动寻找独立来源</span>
            </div>
            <ol className={styles.sourceList}>
              <li>
                <a href={item.source.url} target="_blank" rel="noreferrer">
                  <strong>{item.title}</strong>
                  <span>{item.source.name} · {item.source.level}</span>
                  <ExternalLink size={13} aria-hidden="true" />
                </a>
              </li>
              {(item.relatedSources ?? []).slice(0, 8).map((source) => (
                <li key={`${source.url}-${source.publishedAt}`}>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    <strong>{relatedSourceLabel(source)}</strong>
                    <span>{source.name} · {source.level}</span>
                    <ExternalLink size={13} aria-hidden="true" />
                  </a>
                </li>
              ))}
            </ol>
          </section>

          <section className={styles.promptSection}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">RESEARCH BRIEF</p>
                <h2>交给 Research Workspace 的研究指令</h2>
              </div>
              <button type="button" onClick={() => void copyResearchPrompt()}>
                {copyState === "copied" ? <Check size={14} aria-hidden="true" /> : <Clipboard size={14} aria-hidden="true" />}
                {copyState === "copied" ? "已复制" : copyState === "failed" ? "复制失败" : "复制研究指令"}
              </button>
            </div>
            <pre>{researchPrompt}</pre>
          </section>

          <section className={styles.workspacePanel}>
            <Bot size={22} aria-hidden="true" />
            <div>
              <strong>{workspaceLaunchUrl ? "Research Workspace 上下文入口已准备" : "Research Workspace 尚未发布"}</strong>
              <p>
                {workspaceLaunchUrl
                  ? "打开工作台时会附带事件 ID、VCIQ 上下文页和公开数据集地址，并同时把结构化研究指令复制到剪贴板。"
                  : "当前仍可复制上面的完整研究指令。工作台部署完成并配置 QM_WORKSPACE_URL 后，此处会自动启用上下文入口。"}
              </p>
            </div>
            {workspaceLaunchUrl ? (
              <button type="button" onClick={openWorkspace}>
                复制上下文并进入工作台
                <ExternalLink size={14} aria-hidden="true" />
              </button>
            ) : null}
          </section>
        </>
      ) : null}
    </main>
  );
}
