"use client";

import { Bookmark } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import styles from "@/components/homepage-favorite-controls.module.css";
import { useFavorite } from "@/components/use-favorites";
import {
  isIntelligenceDomRow,
  subscribeIntelligenceDom,
} from "@/lib/intelligence-dom-runtime";
import {
  toggleFavorite,
  type FavoriteChannel,
  type FavoriteInput,
} from "@/lib/favorites";

type FavoritePlacement = "event" | "feed" | "corner" | "cornerArrow";

type FavoriteMount = {
  host: HTMLElement;
  element: HTMLElement;
  item: FavoriteInput;
  key: string;
  placement: FavoritePlacement;
};

type ChannelMeta = {
  channel: FavoriteChannel;
  channelLabel: string;
};

const channelByNumber: Record<string, ChannelMeta> = {
  "02": { channel: "technology", channelLabel: "新兴科技" },
  "03": { channel: "companies", channelLabel: "创业案例" },
  "04": { channel: "institutions", channelLabel: "投资机构" },
  "05": { channel: "ipo", channelLabel: "上市跟踪" },
  "06": { channel: "reports", channelLabel: "研究报告" },
  "07": { channel: "people", channelLabel: "人物研究" },
};

const channelByKey: Record<FavoriteChannel, ChannelMeta> = {
  technology: { channel: "technology", channelLabel: "新兴科技" },
  companies: { channel: "companies", channelLabel: "创业案例" },
  institutions: { channel: "institutions", channelLabel: "投资机构" },
  ipo: { channel: "ipo", channelLabel: "上市跟踪" },
  reports: { channel: "reports", channelLabel: "研究报告" },
  people: { channel: "people", channelLabel: "人物研究" },
};

function cleanText(value: string | null | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function dataValue(element: HTMLElement, suffix: string): string {
  const key = `intelligence${suffix}`;
  return cleanText((element.dataset as Record<string, string | undefined>)[key]);
}

function markedText(row: HTMLElement, suffix: string, selector: string): string {
  const direct = dataValue(row, suffix);
  if (direct) return direct;
  return cleanText(row.querySelector<HTMLElement>(selector)?.textContent);
}

function hrefFrom(anchor: HTMLAnchorElement | null): string {
  if (!anchor) return "";
  const raw = cleanText(anchor.getAttribute("href"));
  if (raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return cleanText(anchor.href || raw);
}

function hrefFromRow(row: HTMLElement): string {
  const explicit = dataValue(row, "Href");
  if (explicit) return explicit;
  if (row instanceof HTMLAnchorElement) return hrefFrom(row);
  const anchor =
    row.querySelector<HTMLAnchorElement>("a[data-intelligence-link][href]") ||
    row.querySelector<HTMLAnchorElement>("a[href^='https://'], a[href^='http://']") ||
    row.querySelector<HTMLAnchorElement>("a[target='_blank'][href]") ||
    row.querySelector<HTMLAnchorElement>("a[href]");
  return hrefFrom(anchor);
}

function stableId(title: string, href: string): string {
  const input = `article|${title}|${href}`;
  let hash = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `homepage:article:${(hash >>> 0).toString(36)}`;
}

function inferChannel(label: string, context = ""): ChannelMeta {
  const combined = `${label} ${context}`;
  const numbered = combined.match(/(?:^|\s)(0[2-7])(?:\s|$)/)?.[1];
  if (numbered && channelByNumber[numbered]) return channelByNumber[numbered];
  if (/人物|采访|演讲|公开对话|观点|著作|股东信|人物材料/.test(combined)) {
    return channelByKey.people;
  }
  if (/研报|报告|政策|公告|PDF|研究材料/.test(combined)) {
    return channelByKey.reports;
  }
  if (/IPO|上市|招股|财报|监管文件|交易所/.test(combined)) {
    return channelByKey.ipo;
  }
  if (/融资|投资|并购|基金|资本|机构/.test(combined)) {
    return channelByKey.institutions;
  }
  if (/技术|论文|模型|AI|芯片|机器人|产品发布|赛道/.test(combined)) {
    return channelByKey.technology;
  }
  return channelByKey.companies;
}

function explicitChannel(row: HTMLElement): ChannelMeta | null {
  const key = dataValue(row, "Channel") as FavoriteChannel;
  if (!channelByKey[key]) return null;
  const label = dataValue(row, "ChannelLabel");
  return label ? { channel: key, channelLabel: label } : channelByKey[key];
}

function channelFromPath(): ChannelMeta | null {
  if (typeof window === "undefined") return null;
  const path = window.location.pathname;
  if (path.startsWith("/technology")) return channelByKey.technology;
  if (path.startsWith("/companies")) return channelByKey.companies;
  if (path.startsWith("/institutions")) return channelByKey.institutions;
  if (path.startsWith("/ipo")) return channelByKey.ipo;
  if (path.startsWith("/reports")) return channelByKey.reports;
  if (path.startsWith("/people")) return channelByKey.people;
  return null;
}

function regionFrom(values: string[]): "中国" | "美国" | "全球" | undefined {
  if (values.some((value) => value.includes("中国"))) return "中国";
  if (values.some((value) => value.includes("美国") || value.includes("美股"))) return "美国";
  if (values.some((value) => value.includes("全球"))) return "全球";
  return undefined;
}

function normalizedDate(value: string): string | undefined {
  const normalized = cleanText(value).replace(/[./]/g, "-");
  const match = normalized.match(/(?:^|\D)(\d{4})-(\d{1,2})-(\d{1,2})(?:\D|$)/);
  if (!match) return undefined;
  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function publishedAtFromEvent(row: HTMLElement): string | undefined {
  const monthDay = cleanText(row.querySelector<HTMLElement>(".event-date strong")?.textContent);
  const year = cleanText(row.querySelector<HTMLElement>(".event-date span")?.textContent);
  return normalizedDate(`${year}-${monthDay}`);
}

function listText(value: string): string[] {
  return value
    .split(/[|｜、,，]/u)
    .map((item) => cleanText(item))
    .filter(Boolean);
}

function makeEventFavorite(row: HTMLElement): FavoriteInput | null {
  const title = cleanText(row.querySelector("h3")?.textContent);
  const summary = cleanText(row.querySelector(".event-main > p")?.textContent);
  const sourceLink = row.querySelector<HTMLAnchorElement>("a.source-link");
  const titleLink = row.querySelector<HTMLAnchorElement>("h3 a[href]");
  const href = hrefFrom(sourceLink) || hrefFrom(titleLink);
  if (!title || !href) return null;

  const tags = [...row.querySelectorAll<HTMLElement>(".event-tags span")]
    .map((element) => cleanText(element.textContent))
    .filter(Boolean);
  const eventType = tags[0] ?? "公司动态";
  const channel = inferChannel(eventType, tags.join(" "));
  const sourceName = cleanText(sourceLink?.textContent) || "公开信源";
  const region = regionFrom(tags);
  const importanceRaw = cleanText(row.querySelector<HTMLElement>(".importance strong")?.textContent);
  const importance = Number(importanceRaw);
  const publishedAt = publishedAtFromEvent(row);

  return {
    id: stableId(title, href),
    href,
    title,
    summary,
    ...channel,
    keywords: tags,
    sectors: tags.slice(2),
    sources: [{ name: sourceName, url: href, level: eventType }],
    ...(region ? { region } : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(Number.isFinite(importance) ? { importance } : {}),
    eventType,
  };
}

function makeFeedFavorite(row: HTMLElement): FavoriteInput | null {
  const title = cleanText(row.querySelector<HTMLElement>("[class*='feedTitle']")?.textContent);
  const context = cleanText(row.querySelector<HTMLElement>("[class*='feedContext']")?.textContent);
  const tag = cleanText(row.querySelector<HTMLElement>("[class*='feedTag']")?.textContent);
  const aside = [...row.querySelectorAll<HTMLElement>("[class*='feedAside'] span")]
    .map((element) => cleanText(element.textContent))
    .filter(Boolean);
  const href = hrefFromRow(row);
  if (!title || !href) return null;

  const channel = inferChannel(tag || aside[1] || "", context);
  const sourceName = cleanText(context.replace(tag, "").replace(/^·|·$/g, "")) || "公开信源";
  const region = regionFrom([context, tag, ...aside]);
  const publishedAt = aside.map(normalizedDate).find(Boolean);

  return {
    id: stableId(title, href),
    href,
    title,
    summary: context || "从首页收藏的公开情报条目。",
    ...channel,
    keywords: [tag, ...aside].filter(Boolean),
    sectors: [],
    sources: href.startsWith("http") ? [{ name: sourceName, url: href }] : [],
    ...(region ? { region } : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(tag ? { eventType: tag } : {}),
  };
}

function makeGenericFavorite(row: HTMLElement): FavoriteInput | null {
  const href = hrefFromRow(row);
  const title = markedText(row, "Title", "[data-intelligence-title], h3, h2, strong");
  if (!href || !title) return null;

  const summary = markedText(
    row,
    "Summary",
    "[data-intelligence-summary], .event-main > p, p, small",
  );
  const eventType = markedText(
    row,
    "Type",
    "[data-intelligence-type], .event-tags span, .tag, [class*='meta'] span",
  ) || "公开材料";
  const context = markedText(
    row,
    "Context",
    "[data-intelligence-context], [class*='context'], [class*='meta']",
  );
  const channel = explicitChannel(row) || channelFromPath() || inferChannel(eventType, `${context} ${title}`);
  const sourceName = markedText(
    row,
    "Source",
    "[data-intelligence-source], .source-link, [class*='source'], small",
  ) || "公开信源";
  const sourceLevel = dataValue(row, "SourceLevel") || eventType;
  const dateCandidate =
    dataValue(row, "Date") ||
    cleanText(row.querySelector<HTMLTimeElement>("time")?.dateTime) ||
    cleanText(row.querySelector("time")?.textContent);
  const publishedAt = normalizedDate(dateCandidate);
  const explicitKeywords = listText(dataValue(row, "Keywords"));
  const visibleTags = [...row.querySelectorAll<HTMLElement>(
    "[data-intelligence-tag], .event-tags span, .tag, [class*='meta'] span, i",
  )]
    .map((element) => cleanText(element.textContent))
    .filter(Boolean);
  const sectors = listText(dataValue(row, "Sector"));
  const explicitRegion = dataValue(row, "Region");
  const region =
    explicitRegion === "中国" || explicitRegion === "美国" || explicitRegion === "全球"
      ? explicitRegion
      : regionFrom([...visibleTags, context]);
  const importanceValue = Number(dataValue(row, "Importance"));
  const company = dataValue(row, "Company");

  return {
    id: dataValue(row, "Id") || stableId(title, href),
    href,
    title,
    summary,
    ...channel,
    keywords: [...new Set([eventType, ...explicitKeywords, ...visibleTags])],
    sectors,
    sources: href.startsWith("http")
      ? [{ name: sourceName, url: href, ...(sourceLevel ? { level: sourceLevel } : {}) }]
      : [],
    ...(region ? { region } : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(Number.isFinite(importanceValue) && dataValue(row, "Importance")
      ? { importance: importanceValue }
      : {}),
    ...(company ? { company } : {}),
    eventType,
  };
}

function InlineFavoriteButton({ item }: { item: FavoriteInput }) {
  const saved = useFavorite(item.id);

  return (
    <button
      type="button"
      className={styles.button}
      data-saved={saved ? "true" : "false"}
      aria-pressed={saved}
      aria-label={saved ? `取消收藏：${item.title}` : `收藏：${item.title}`}
      title={saved ? "取消收藏" : "收藏这条情报到 08 收藏频道"}
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleFavorite(item);
      }}
    >
      <Bookmark size={12} fill={saved ? "currentColor" : "none"} />
      <span>{saved ? "已收藏" : "收藏"}</span>
    </button>
  );
}

function placementFor(row: HTMLElement): FavoritePlacement {
  if (row.matches(".event-row")) return "event";
  if (
    row.matches(
      ".headlines-column [data-intelligence-item][class*='feedRow'], .side-column [data-intelligence-item][class*='feedRow']",
    )
  ) {
    return "feed";
  }
  return row.querySelector("svg, [class*='arrow']") ? "cornerArrow" : "corner";
}

function itemFor(row: HTMLElement): FavoriteInput | null {
  if (row.matches(".event-row")) return makeEventFavorite(row);
  if (
    row.matches(
      ".headlines-column [data-intelligence-item][class*='feedRow'], .side-column [data-intelligence-item][class*='feedRow']",
    )
  ) {
    return makeFeedFavorite(row);
  }
  return makeGenericFavorite(row);
}

export function IntelligenceFavoriteControls() {
  const [mounts, setMounts] = useState<FavoriteMount[]>([]);

  useEffect(() => {
    const registry = new Map<HTMLElement, FavoriteMount>();
    let sequence = 0;

    const removeMount = (mount: FavoriteMount) => {
      mount.element.remove();
      mount.host.classList.remove(styles.cornerHost, styles.cornerSpace);
      delete mount.host.dataset.intelligenceFavoriteAttached;
    };

    const publish = () => setMounts([...registry.values()]);

    const addMount = (
      host: HTMLElement,
      item: FavoriteInput,
      placement: FavoritePlacement,
    ): FavoriteMount => {
      const element = document.createElement("span");
      const key = `${placement}:${sequence}:${item.id}`;
      sequence += 1;
      element.dataset.intelligenceFavoriteMount = "true";
      element.className = [
        styles.mount,
        placement === "event"
          ? styles.eventMount
          : placement === "feed"
            ? styles.feedMount
            : placement === "cornerArrow"
              ? styles.cornerArrowMount
              : styles.cornerMount,
      ].join(" ");

      if (placement === "event") {
        const actions = host.querySelector<HTMLElement>("[data-intelligence-event-actions]");
        const target = actions ?? host.querySelector<HTMLElement>(".importance");
        if (actions) target?.appendChild(element);
        else target?.prepend(element);
      } else if (placement === "feed") {
        const target = host.querySelector<HTMLElement>("[class*='feedContext']");
        target?.appendChild(element);
      } else {
        host.classList.add(styles.cornerHost, styles.cornerSpace);
        host.appendChild(element);
      }

      host.dataset.intelligenceFavoriteAttached = "true";
      return { host, element, item, key, placement };
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
        if (!isIntelligenceDomRow(row, "favorite")) continue;
        const item = itemFor(row);
        if (!item) continue;
        const placement = placementFor(row);
        const existing = registry.get(row);
        if (existing) {
          if (
            existing.item.id !== item.id ||
            existing.item.href !== item.href ||
            existing.item.title !== item.title ||
            existing.item.summary !== item.summary
          ) {
            registry.set(row, { ...existing, item });
            changed = true;
          }
          continue;
        }
        const mount = addMount(row, item, placement);
        if (!mount.element.isConnected) continue;
        registry.set(row, mount);
        changed = true;
      }

      if (changed) publish();
    };

    const unsubscribe = subscribeIntelligenceDom(scan, { priority: 10 });

    return () => {
      unsubscribe();
      registry.forEach(removeMount);
      registry.clear();
    };
  }, []);

  return (
    <>
      {mounts.map(({ element, item, key }) =>
        createPortal(<InlineFavoriteButton item={item} />, element, key),
      )}
    </>
  );
}

export const HomepageFavoriteControls = IntelligenceFavoriteControls;
