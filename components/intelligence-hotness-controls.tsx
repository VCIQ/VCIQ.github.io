"use client";

import { Share2 } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import styles from "@/components/intelligence-hotness-controls.module.css";
import {
  isIntelligenceDomRow,
  subscribeIntelligenceDom,
} from "@/lib/intelligence-dom-runtime";
import {
  recordArticleOpen,
  recordArticleShare,
  setArticleFavorite,
  type HotnessInput,
} from "@/lib/hotness";
import { syncSharePreference } from "@/lib/share-preference-sync";

const SHARE_REQUEST_EVENT = "vciq:favorite-share-request";

type ShareMount = {
  host: HTMLElement;
  element: HTMLElement;
  item: HotnessInput;
  key: string;
};

function cleanText(value: string | null | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function hrefFrom(anchor: HTMLAnchorElement | null): string {
  if (!anchor) return "";
  const raw = cleanText(anchor.getAttribute("href"));
  if (raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return cleanText(anchor.href || raw);
}

function hrefFromRow(row: HTMLElement): string {
  const explicit = cleanText(row.dataset.intelligenceHref);
  if (explicit) return explicit;
  if (row instanceof HTMLAnchorElement) return hrefFrom(row);
  return hrefFrom(
    row.querySelector<HTMLAnchorElement>("a[data-intelligence-link][href]") ||
      row.querySelector<HTMLAnchorElement>("a.source-link[href]") ||
      row.querySelector<HTMLAnchorElement>("h3 a[href], h2 a[href]") ||
      row.querySelector<HTMLAnchorElement>("a[target='_blank'][href]") ||
      row.querySelector<HTMLAnchorElement>("a[href]"),
  );
}

function dateFromRow(row: HTMLElement): string | undefined {
  const explicit = cleanText(row.dataset.intelligenceDate);
  if (/^\d{4}-\d{2}-\d{2}$/.test(explicit)) return explicit;
  const monthDay = cleanText(row.querySelector<HTMLElement>(".event-date strong")?.textContent);
  const year = cleanText(row.querySelector<HTMLElement>(".event-date span")?.textContent);
  if (/^\d{4}$/.test(year) && /^\d{2}-\d{2}$/.test(monthDay)) return `${year}-${monthDay}`;
  const time = row.querySelector<HTMLTimeElement>("time");
  const candidate = cleanText(time?.dateTime || time?.textContent);
  const match = candidate.match(/\d{4}-\d{2}-\d{2}/)?.[0];
  return match || undefined;
}

function itemFromRow(row: HTMLElement): HotnessInput | null {
  const href = hrefFromRow(row);
  const title =
    cleanText(row.dataset.intelligenceTitle) ||
    cleanText(
      row.querySelector<HTMLElement>(
        "[data-intelligence-title], [class*='feedTitle'], h3, h2, strong",
      )?.textContent,
    );
  if (!href || !title) return null;

  const summary =
    cleanText(row.dataset.intelligenceSummary) ||
    cleanText(
      row.querySelector<HTMLElement>(
        "[data-intelligence-summary], .event-main > p, [class*='feedContext'], p",
      )?.textContent,
    );
  const sourceName =
    cleanText(row.dataset.intelligenceSource) ||
    cleanText(
      row.querySelector<HTMLElement>(
        "[data-intelligence-source], .source-link, [class*='source'], small",
      )?.textContent,
    );
  const importanceText =
    cleanText(row.dataset.intelligenceImportance) ||
    cleanText(row.querySelector<HTMLElement>(".importance strong")?.textContent);
  const importance = Number(importanceText);

  return {
    id: cleanText(row.dataset.intelligenceId) || undefined,
    href,
    title,
    summary,
    publishedAt: dateFromRow(row),
    importance: Number.isFinite(importance) ? importance : undefined,
    sourceName,
    channelLabel: cleanText(row.dataset.intelligenceChannelLabel) || undefined,
  };
}

function rowFromTarget(target: EventTarget | null): HTMLElement | null {
  const element = target instanceof Element ? target : null;
  if (!element) return null;
  return (
    element.closest<HTMLElement>(".event-row") ||
    element.closest<HTMLElement>(".headlines-column a[class*='feedRow']") ||
    element.closest<HTMLElement>(".side-column a[class*='feedRow']") ||
    element.closest<HTMLElement>("[data-intelligence-item]") ||
    element.closest<HTMLElement>(".material-list > a") ||
    element.closest<HTMLElement>("a.source-card[href]") ||
    element.closest<HTMLElement>("a[class*='eventCard'][href]") ||
    element.closest<HTMLElement>(".market-news-item[href]") ||
    element.closest<HTMLElement>("[class*='eventList'] > a[href]") ||
    element.closest<HTMLElement>("[class*='newsList'] > a[href]") ||
    element.closest<HTMLElement>(".entity-list > a[target='_blank'][href]") ||
    element.closest<HTMLElement>(".analysis-grid > a[target='_blank'][href]") ||
    element.closest<HTMLElement>(".favorite-intelligence-card") ||
    element.closest<HTMLElement>(".favorite-card") ||
    element.closest<HTMLElement>(".timeline > div")
  );
}

function learnFromShare(item: HotnessInput) {
  void syncSharePreference({
    id: item.id || item.href,
    href: item.href,
    title: item.title,
    summary: item.summary,
    channelLabel: item.channelLabel,
    sources: item.sourceName
      ? [{ name: item.sourceName, url: item.href }]
      : [],
    publishedAt: item.publishedAt,
    importance: item.importance,
    sharedAt: new Date().toISOString(),
  });
}

function InlineShareButton({ item }: { item: HotnessInput }) {
  return (
    <button
      type="button"
      className={styles.button}
      aria-label={`分享：${item.title}`}
      title="分享并计入 09 热点"
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        recordArticleShare(item);
        learnFromShare(item);
        window.dispatchEvent(
          new CustomEvent(SHARE_REQUEST_EVENT, {
            detail: {
              title: item.title,
              summary: item.summary ?? "",
              url: item.href,
            },
          }),
        );
      }}
    >
      <Share2 size={12} />
      <span>分享</span>
    </button>
  );
}

export function IntelligenceHotnessControls() {
  const [mounts, setMounts] = useState<ShareMount[]>([]);

  useEffect(() => {
    const registry = new Map<HTMLElement, ShareMount>();
    let sequence = 0;

    const removeMount = (mount: ShareMount) => {
      mount.element.remove();
      delete mount.host.dataset.intelligenceHotnessAttached;
    };

    const scan = (rows: readonly HTMLElement[]) => {
      let changed = false;

      for (const [host, mount] of registry) {
        if (!host.isConnected || !mount.element.isConnected) {
          removeMount(mount);
          registry.delete(host);
          changed = true;
        }
      }

      for (const row of rows) {
        if (!isIntelligenceDomRow(row, "hotness")) continue;
        const item = itemFromRow(row);
        if (!item) continue;
        const favoriteMount = row.querySelector<HTMLElement>("[data-intelligence-favorite-mount]");
        if (!favoriteMount) continue;
        const existing = registry.get(row);
        if (existing) {
          if (
            existing.item.href !== item.href ||
            existing.item.title !== item.title ||
            existing.item.summary !== item.summary
          ) {
            registry.set(row, { ...existing, item });
            changed = true;
          }
          continue;
        }

        const element = document.createElement("span");
        element.dataset.intelligenceHotnessMount = "true";
        element.className = styles.mount;
        favoriteMount.insertAdjacentElement("afterend", element);
        row.dataset.intelligenceHotnessAttached = "true";
        const mount = {
          host: row,
          element,
          item,
          key: `share:${sequence}:${item.href}`,
        };
        sequence += 1;
        registry.set(row, mount);
        changed = true;
      }

      if (changed) setMounts([...registry.values()]);
    };

    const onClickCapture = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target : null;
      if (!element) return;
      const row = rowFromTarget(element);
      if (!row) return;
      const item = itemFromRow(row);
      if (!item) return;

      const favoriteButton = element.closest<HTMLButtonElement>(
        "[data-intelligence-favorite-mount] button",
      );
      if (favoriteButton) {
        const willBeFavorite = !favoriteButton.getAttribute("aria-label")?.startsWith("取消收藏");
        setArticleFavorite(item, willBeFavorite);
        return;
      }

      if (element.closest("button.favorite-remove")) {
        setArticleFavorite(item, false);
        return;
      }

      if (element.closest("button.favorite-share")) {
        recordArticleShare(item);
        learnFromShare(item);
        return;
      }

      const anchor = element.closest<HTMLAnchorElement>("a[href]");
      if (anchor && !anchor.closest("[data-hotness-ignore='true']")) {
        recordArticleOpen(item);
      }
    };

    const unsubscribe = subscribeIntelligenceDom(scan, { priority: 30 });
    document.addEventListener("click", onClickCapture, true);

    return () => {
      unsubscribe();
      document.removeEventListener("click", onClickCapture, true);
      registry.forEach(removeMount);
      registry.clear();
    };
  }, []);

  return (
    <>
      {mounts.map(({ element, item, key }) =>
        createPortal(<InlineShareButton item={item} />, element, key),
      )}
    </>
  );
}
