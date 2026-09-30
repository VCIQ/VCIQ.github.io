import policy from "@/config/focus_direct_media.json";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export type FocusDirectMediaMatch = {
  publisherId: string;
  publisherName: string;
  attribution: "direct-host" | "rss-publisher-label";
};

const CAPITAL_OR_INDUSTRIAL_EVENT =
  /科创板|创业板|北交所|A\+H|Pre-?IPO|IPO|上市|辅导|备案|问询|注册|过会|递表|聆讯|融资|募资|并购|收购|股权|增资|产业投资|战略投资|基金|量产|订单|获批/iu;

function hostname(url: string): string {
  try { return new URL(url).hostname.toLowerCase().replace(/^www\./u, ""); } catch { return ""; }
}
function clean(value: string): string {
  return value.normalize("NFKC").replace(/\s+/gu, " ").trim();
}
function publisherSuffix(title: string, label: string): boolean {
  const source = clean(title); const name = clean(label);
  return source === name || source.endsWith(` - ${name}`) || source.endsWith(`｜${name}`) ||
    source.endsWith(`|${name}`) || source.endsWith(` — ${name}`) || source.endsWith(` · ${name}`);
}

/**
 * Owner-approved innovation/capital publisher lane. Direct host attribution is
 * preferred. Google News/Alerts discovery is accepted only when its title has
 * an exact publisher suffix; a random prose mention of the publisher is never
 * enough. This admits a story to Focus, not to Core and not as verified fact.
 */
export function focusDirectMediaMatch(item: LiveIntelligenceEvent): FocusDirectMediaMatch | null {
  if (!policy.runtimeEnabled) return null;
  if (!CAPITAL_OR_INDUSTRIAL_EVENT.test(`${item.type} ${item.title} ${item.summary}`)) return null;
  const host = hostname(item.source.url);
  for (const publisher of policy.publishers) {
    if (publisher.hosts.some((allowed) => host === allowed || host.endsWith(`.${allowed}`))) {
      return { publisherId: publisher.id, publisherName: publisher.name, attribution: "direct-host" };
    }
  }
  const discovery = item.source.level === "待交叉验证" || /google news|google alerts/iu.test(`${item.source.platform ?? ""} ${item.source.name}`);
  if (!discovery) return null;
  for (const publisher of policy.publishers) {
    if (publisher.labels.some((label) => publisherSuffix(item.title, label))) {
      return { publisherId: publisher.id, publisherName: publisher.name, attribution: "rss-publisher-label" };
    }
  }
  return null;
}
