"use client";

import {
  Bookmark,
  Download,
  Search,
  Share2,
  Trash2,
  Undo2,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  HomepageSortToggle,
  type HomepageSortMode,
} from "@/components/homepage-sort-toggle";
import { useFavorites } from "@/components/use-favorites";
import {
  importFavoriteItems,
  removeFavorite,
  restoreFavorite,
  serializeFavoriteItems,
  type FavoriteItem,
} from "@/lib/favorites";

export const FAVORITE_SHARE_REQUEST_EVENT = "vciq:favorite-share-request";
const FAVORITES_BATCH_SIZE = 60;

export type FavoriteShareRequest = {
  title: string;
  summary: string;
  url: string;
};

function isIntelligenceCard(item: FavoriteItem): boolean {
  return Boolean(
    item.id.startsWith("homepage:article:") ||
      item.publishedAt ||
      item.eventType ||
      item.importance !== undefined,
  );
}

function favoriteSortAt(item: FavoriteItem): string {
  return item.publishedAt ?? item.savedAt;
}

function sortFavorites(
  items: FavoriteItem[],
  mode: HomepageSortMode,
): FavoriteItem[] {
  return [...items].sort((left, right) => {
    const leftTime = favoriteSortAt(left);
    const rightTime = favoriteSortAt(right);
    const leftImportance = left.importance ?? -1;
    const rightImportance = right.importance ?? -1;

    if (mode === "importance") {
      return (
        rightImportance - leftImportance ||
        rightTime.localeCompare(leftTime) ||
        left.title.localeCompare(right.title, "zh-CN")
      );
    }

    return (
      rightTime.localeCompare(leftTime) ||
      rightImportance - leftImportance ||
      left.title.localeCompare(right.title, "zh-CN")
    );
  });
}

function absoluteShareUrl(href: string): string {
  if (typeof window === "undefined") return href;
  try {
    return new URL(href, window.location.origin).href;
  } catch {
    return href;
  }
}

function ShareFavoriteButton({ item }: { item: FavoriteItem }) {
  const openQrShare = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();

    const detail: FavoriteShareRequest = {
      title: item.title,
      summary: item.summary,
      url: absoluteShareUrl(item.href),
    };

    window.dispatchEvent(
      new CustomEvent<FavoriteShareRequest>(FAVORITE_SHARE_REQUEST_EVENT, { detail }),
    );
  };

  return (
    <div className="favorite-share-control">
      <button
        type="button"
        className="favorite-share"
        onClick={openQrShare}
        aria-label={`分享：${item.title}`}
        title="打开微信二维码分享"
      >
        <Share2 size={14} />
        <span>分享</span>
      </button>
    </div>
  );
}

function FavoriteCardActions({
  item,
  onRemove,
}: {
  item: FavoriteItem;
  onRemove: (item: FavoriteItem) => void;
}) {
  return (
    <div className="favorite-card-actions">
      <ShareFavoriteButton item={item} />
      <button
        type="button"
        className="favorite-remove"
        onClick={() => onRemove(item)}
        aria-label={`移除收藏：${item.title}`}
        title="移除收藏"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}

function IntelligenceFavoriteCard({
  item,
  onRemove,
}: {
  item: FavoriteItem;
  onRemove: (item: FavoriteItem) => void;
}) {
  const date = item.publishedAt || item.savedAt.slice(0, 10);
  const source = item.sources[0];
  const eventType = item.eventType || item.keywords[0];
  const tags = [...new Set([
    eventType,
    item.region,
    ...item.sectors,
  ].filter(Boolean))] as string[];

  return (
    <article className="favorite-intelligence-card">
      <a
        className="favorite-intelligence-link"
        href={item.href}
        target="_blank"
        rel="noreferrer"
        aria-label={`打开原始情报：${item.title}`}
      >
        <div className="event-date">
          <strong>{date.slice(5)}</strong>
          <span>{date.slice(0, 4)}</span>
        </div>

        <div className="event-main">
          <div className="event-tags">
            {tags.map((tag, index) => (
              <span className={index === 0 ? `tag tag-${tag}` : undefined} key={tag}>
                {tag}
              </span>
            ))}
          </div>
          <h3>{item.title}</h3>
          <p>{item.summary || "打开原始链接查看完整内容。"}</p>
          <span className="source-link favorite-source-link">
            {source
              ? `${source.level ? `${source.level} · ` : ""}${source.name}`
              : "打开原始链接"}
            <span aria-hidden="true">↗</span>
          </span>
        </div>

        <div className="importance">
          {item.importance !== undefined ? (
            <>
              <span>重要度</span>
              <strong>{item.importance}</strong>
            </>
          ) : (
            <span>原始情报 ↗</span>
          )}
        </div>
      </a>

      <FavoriteCardActions item={item} onRemove={onRemove} />
    </article>
  );
}

export function FavoritesPage() {
  const favorites = useFavorites();
  const [channel, setChannel] = useState("全部频道");
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<HomepageSortMode>("latest");
  const [visibleLimit, setVisibleLimit] = useState(FAVORITES_BATCH_SIZE);
  const [removedItem, setRemovedItem] = useState<FavoriteItem | null>(null);
  const [transferNotice, setTransferNotice] = useState("");
  const importInputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!removedItem) return;
    const timeout = window.setTimeout(() => setRemovedItem(null), 8_000);
    return () => window.clearTimeout(timeout);
  }, [removedItem]);
  const channels = useMemo(
    () => [
      "全部频道",
      ...new Set(favorites.map((item) => item.channelLabel).filter(Boolean)),
    ],
    [favorites],
  );
  const visible = useMemo(() => {
    const needle = query.normalize("NFKC").trim().toLocaleLowerCase("zh-CN");
    const filtered = favorites.filter((item) => {
      if (channel !== "全部频道" && item.channelLabel !== channel) return false;
      if (!needle) return true;
      return [
        item.title,
        item.summary,
        item.channelLabel,
        item.eventType ?? "",
        ...item.keywords,
        ...item.sectors,
      ].some((value) => value.toLocaleLowerCase("zh-CN").includes(needle));
    });
    return sortFavorites(filtered, sortMode);
  }, [channel, favorites, query, sortMode]);
  const renderedVisible = visible.slice(0, visibleLimit);
  const hasMore = renderedVisible.length < visible.length;
  const signals = useMemo(() => {
    const topics = new Map<string, number>();
    const sources = new Map<string, number>();
    for (const item of favorites) {
      for (const topic of [...item.sectors, ...item.keywords].slice(0, 12)) {
        topics.set(topic, (topics.get(topic) ?? 0) + 1);
      }
      for (const source of item.sources) {
        let label = source.name;
        try {
          label = new URL(source.url).hostname.replace(/^www\./, "") || label;
        } catch {}
        sources.set(label, (sources.get(label) ?? 0) + 1);
      }
    }
    const rank = (values: Map<string, number>) =>
      [...values.entries()]
        .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], "zh-CN"))
        .slice(0, 3)
        .map(([label]) => label);
    return { topics: rank(topics), sources: rank(sources) };
  }, [favorites]);

  const handleRemove = (item: FavoriteItem) => {
    const removed = removeFavorite(item.id);
    if (removed) setRemovedItem(removed);
  };

  const handleUndoRemove = () => {
    if (removedItem && restoreFavorite(removedItem)) setTransferNotice("已恢复刚才移除的收藏");
    setRemovedItem(null);
  };

  const handleExport = () => {
    const blob = new Blob([serializeFavoriteItems(favorites)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `vciq-favorites-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setTransferNotice(`已导出 ${favorites.length} 项收藏`);
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const result = importFavoriteItems(await file.text());
      setTransferNotice(
        result.added
          ? `已导入 ${result.added} 项，跳过 ${result.skipped} 项重复或无效记录`
          : "没有新增收藏；文件中的记录可能已存在或无法识别",
      );
    } catch (error) {
      setTransferNotice(error instanceof Error ? error.message : "收藏文件导入失败");
    }
  };

  return (
    <>
      <header className="page-header favorites-header">
        <p className="eyebrow">08 / FAVORITES</p>
        <div>
          <h1>收藏</h1>
          <p className="intro-copy">
            保存值得持续跟踪的情报卡片；收藏主题、关键词与信源会参与站内推荐排序。
          </p>
        </div>
        <div className="favorites-signal-card">
          <span>当前浏览器</span>
          <strong>{favorites.length}</strong>
          <p>项收藏 · 仅保存在当前浏览器</p>
        </div>
      </header>

      <section className="favorites-safety" aria-label="收藏保存与推荐信号">
        <div>
          <strong>请定期备份收藏</strong>
          <p>清除浏览器数据、更换浏览器或设备后，本地收藏可能丢失。</p>
        </div>
        <div className="favorites-transfer-actions">
          <button type="button" onClick={handleExport} disabled={!favorites.length}>
            <Download size={15} />导出备份
          </button>
          <button type="button" onClick={() => importInputRef.current?.click()}>
            <Upload size={15} />导入收藏
          </button>
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            onChange={handleImport}
            className="favorites-file-input"
            tabIndex={-1}
          />
        </div>
      </section>

      {favorites.length ? (
        <section className="favorites-preference-summary" aria-label="收藏信号概览">
          <div><span>推荐状态</span><strong>已参与站内推荐排序</strong></div>
          <div><span>高频主题</span><strong>{signals.topics.join(" · ") || "尚待积累"}</strong></div>
          <div><span>高频信源</span><strong>{signals.sources.join(" · ") || "尚待积累"}</strong></div>
        </section>
      ) : null}

      {favorites.length ? (
        <>
          <div className="favorites-toolbar">
            <div className="favorites-tabs" aria-label="按频道筛选收藏">
              {channels.map((item) => (
                <button
                  type="button"
                  className={channel === item ? "active" : ""}
                  onClick={() => {
                    setChannel(item);
                    setVisibleLimit(FAVORITES_BATCH_SIZE);
                  }}
                  key={item}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="favorites-toolbar-actions">
              <HomepageSortToggle
                value={sortMode}
                onChange={(value) => {
                  setSortMode(value);
                  setVisibleLimit(FAVORITES_BATCH_SIZE);
                }}
                ariaLabel="收藏排序方式"
              />
              <label className="favorites-search">
                <Search size={15} />
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setVisibleLimit(FAVORITES_BATCH_SIZE);
                  }}
                  placeholder="搜索收藏标题、摘要或关键词"
                  aria-label="搜索收藏"
                />
              </label>
            </div>
          </div>

          <div className="favorites-list">
            {renderedVisible.map((item, index) =>
              isIntelligenceCard(item) ? (
                <IntelligenceFavoriteCard item={item} onRemove={handleRemove} key={item.id} />
              ) : (
                <article className="favorite-card" key={item.id}>
                  <span className="favorite-card-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <Link href={item.href} className="favorite-card-main">
                    <div className="favorite-card-meta">
                      <span>{item.channelLabel}</span>
                      <time>{new Date(item.savedAt).toLocaleDateString("zh-CN")}</time>
                    </div>
                    <h2>{item.title}</h2>
                    <p>{item.summary || "打开原页面继续阅读。"}</p>
                    <div className="favorite-card-tags">
                      {[...new Set([...item.sectors, ...item.keywords])]
                        .slice(0, 6)
                        .map((tag) => (
                          <span key={tag}>{tag}</span>
                        ))}
                      {item.sources.length ? (
                        <span>{item.sources.length} 个参考信源</span>
                      ) : null}
                    </div>
                  </Link>
                  <FavoriteCardActions item={item} onRemove={handleRemove} />
                </article>
              ),
            )}
          </div>

          {hasMore ? (
            <div className="favorites-load-more">
              <button
                type="button"
                onClick={() => setVisibleLimit((current) => current + FAVORITES_BATCH_SIZE)}
              >
                显示更多 · 已显示 {renderedVisible.length}/{visible.length}
              </button>
            </div>
          ) : null}

          {!visible.length ? (
            <div className="favorites-empty compact">
              <Search size={24} />
              <strong>没有符合当前条件的收藏</strong>
              <p>更换频道或搜索词后再试。</p>
              <button
                type="button"
                className="favorites-clear-filters"
                onClick={() => {
                  setChannel("全部频道");
                  setQuery("");
                }}
              >
                清除筛选
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="favorites-empty">
          <Bookmark size={30} />
          <strong>还没有收藏情报</strong>
          <p>在任一条目式情报卡片右上角点击“收藏”，即可把整张卡片保存到这里。</p>
          <div className="favorites-empty-links">
            <Link href="/">浏览近期情报 →</Link>
            <Link href="/technologies/">浏览核心赛道 →</Link>
            <Link href="/companies/">浏览核心公司 →</Link>
            <Link href="/people/">浏览核心人物 →</Link>
          </div>
        </div>
      )}

      {removedItem ? (
        <div className="favorites-toast" role="status">
          <span>已移除《{removedItem.title}》</span>
          <button type="button" onClick={handleUndoRemove}><Undo2 size={14} />撤销</button>
          <button type="button" aria-label="关闭提示" onClick={() => setRemovedItem(null)}><X size={14} /></button>
        </div>
      ) : transferNotice ? (
        <div className="favorites-toast" role="status">
          <span>{transferNotice}</span>
          <button type="button" aria-label="关闭提示" onClick={() => setTransferNotice("")}><X size={14} /></button>
        </div>
      ) : null}

      <style jsx global>{`
        .favorites-toolbar-actions {
          margin-left: auto;
          display: flex;
          flex: 0 0 auto;
          align-items: center;
          gap: 10px;
        }

        .favorites-toolbar-actions .favorites-search {
          margin-left: 0;
        }

        .favorites-safety {
          border: 1px solid var(--border);
          border-left: 3px solid var(--green);
          background: var(--surface-2);
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          margin: 0 0 18px;
          padding: 14px 16px;
        }

        .favorites-safety strong { font-size: 13px; }
        .favorites-safety p { color: var(--muted); margin: 4px 0 0; font-size: 12px; }
        .favorites-transfer-actions { display: flex; gap: 8px; flex: none; }
        .favorites-transfer-actions button,
        .favorites-clear-filters {
          border: 1px solid var(--border);
          background: var(--surface);
          min-height: 36px;
          color: var(--text);
          cursor: pointer;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 7px 11px;
          font: 500 12px/1.2 Inter, "Noto Sans SC", sans-serif;
          display: inline-flex;
        }
        .favorites-transfer-actions button:hover,
        .favorites-clear-filters:hover { border-color: var(--green); color: var(--green-bright); }
        .favorites-transfer-actions button:disabled { cursor: not-allowed; opacity: 0.45; }
        .favorites-file-input { display: none; }

        .favorites-preference-summary {
          border-top: 1px solid var(--border);
          border-bottom: 1px solid var(--border);
          grid-template-columns: repeat(3, minmax(0, 1fr));
          margin: 0 0 20px;
          display: grid;
        }
        .favorites-preference-summary > div { min-width: 0; padding: 13px 16px; }
        .favorites-preference-summary > div + div { border-left: 1px solid var(--border); }
        .favorites-preference-summary span { color: var(--muted); display: block; font-size: 10px; letter-spacing: .08em; }
        .favorites-preference-summary strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 6px; display: block; font-size: 12px; }

        .favorites-empty-links { flex-wrap: wrap; justify-content: center; gap: 8px 18px; display: flex; }
        .favorites-toast {
          z-index: 1100;
          border: 1px solid var(--border);
          background: var(--surface);
          box-shadow: var(--shadow);
          max-width: min(520px, calc(100vw - 32px));
          align-items: center;
          gap: 10px;
          padding: 11px 12px 11px 15px;
          display: flex;
          position: fixed;
          right: 22px;
          bottom: 22px;
        }
        .favorites-toast span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
        .favorites-toast button { border: 0; background: transparent; color: var(--green-bright); cursor: pointer; align-items: center; gap: 4px; padding: 5px; display: inline-flex; }

        .favorite-intelligence-card,
        .favorite-card {
          content-visibility: auto;
          contain-intrinsic-size: 150px;
        }

        .favorite-intelligence-card {
          position: relative;
          border-bottom: 1px solid var(--border);
          transition: background 0.2s ease;
        }

        .favorite-intelligence-card:hover {
          background: color-mix(in srgb, var(--surface) 70%, transparent);
        }

        .favorite-intelligence-link {
          display: grid;
          grid-template-columns: 74px minmax(0, 1fr) 76px;
          gap: 19px;
          padding: 20px 4px;
        }

        .favorite-intelligence-link:hover h3 {
          color: var(--green-bright);
        }

        .favorite-intelligence-card .event-main {
          min-width: 0;
          padding-right: 4px;
        }

        .favorite-intelligence-card .event-main h3 {
          margin: 0 0 6px;
          font-size: 17px;
          line-height: 1.4;
        }

        .favorite-intelligence-card .event-main p {
          margin: 0 0 8px;
        }

        .favorite-source-link {
          pointer-events: none;
        }

        .favorite-intelligence-card .importance {
          padding-top: 38px;
          padding-right: 4px;
        }

        .favorite-card {
          position: relative;
          grid-template-columns: 42px minmax(0, 1fr) 108px;
        }

        .favorite-card-actions {
          position: relative;
          z-index: 3;
          display: flex;
          align-items: flex-start;
          justify-content: flex-end;
          gap: 6px;
          align-self: start;
        }

        .favorite-intelligence-card > .favorite-card-actions {
          position: absolute;
          top: 14px;
          right: 7px;
        }

        .favorite-share-control {
          position: relative;
        }

        .favorite-share {
          min-height: 30px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          padding: 5px 9px;
          border: 1px solid color-mix(in srgb, var(--blue) 58%, var(--border));
          background: color-mix(in srgb, var(--blue) 8%, var(--surface));
          color: var(--blue);
          cursor: pointer;
          font: 500 10px/1 Inter, "Noto Sans SC", sans-serif;
          white-space: nowrap;
        }

        .favorite-share:hover {
          border-color: var(--blue);
          background: color-mix(in srgb, var(--blue) 14%, var(--surface));
          color: var(--text);
        }

        .favorite-share:focus-visible {
          outline: 1px solid var(--blue);
          outline-offset: 2px;
        }

        .favorite-card-actions .favorite-remove {
          flex: 0 0 auto;
          width: 30px;
          height: 30px;
        }

        .favorites-load-more {
          display: flex;
          justify-content: center;
          padding: 20px 0 6px;
        }

        .favorites-load-more button {
          min-height: 38px;
          padding: 8px 16px;
          border: 1px solid var(--border);
          background: var(--surface-2);
          color: var(--text);
          cursor: pointer;
          font: inherit;
          font-size: 12px;
        }

        .favorites-load-more button:hover {
          border-color: var(--green);
          color: var(--green-bright);
        }

        @media (max-width: 900px) {
          .favorites-toolbar-actions {
            width: 100%;
            margin-left: 0;
          }

          .favorites-toolbar-actions .favorites-search {
            flex: 1 1 260px;
            width: auto;
          }
        }

        @media (max-width: 720px) {
          .favorites-safety { align-items: stretch; flex-direction: column; }
          .favorites-transfer-actions button { flex: 1; min-height: 44px; }
          .favorites-preference-summary { grid-template-columns: 1fr; }
          .favorites-preference-summary > div + div { border-left: 0; border-top: 1px solid var(--border); }
          .favorites-toast { right: 12px; bottom: 12px; left: 12px; max-width: none; }
          .favorite-intelligence-link {
            grid-template-columns: 54px minmax(0, 1fr) 54px;
            gap: 12px;
          }

          .favorite-intelligence-card .event-tags {
            flex-wrap: wrap;
          }

          .favorite-intelligence-card .event-main h3 {
            font-size: 15px;
          }

          .favorite-card {
            grid-template-columns: 34px minmax(0, 1fr) 74px;
          }

          .favorite-share {
            width: 30px;
            min-width: 30px;
            padding: 5px;
          }

          .favorite-share span {
            display: none;
          }
        }

        @media (max-width: 560px) {
          .favorites-toolbar-actions {
            flex-direction: column;
            align-items: stretch;
          }

          .favorites-toolbar-actions .favorites-search {
            width: 100%;
          }
        }
      `}</style>
    </>
  );
}
