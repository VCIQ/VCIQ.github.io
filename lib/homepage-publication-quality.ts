/** Small, shared public-surface admission rules. Never import the full archive here. */
export type HomepagePublicationCandidate = { title: string; summary: string; type: string; source: {url: string}; qualityStatus?: string; };
export type HomepageAdmission = { admitted: boolean; reason: string | null; correctedType: string | null; };

/** Plain-text projection only. Never interpret decoded text as HTML. */
export function normalizeHomepageText(value: string): string {
  const entities: Record<string, string> = {nbsp:" ",amp:"&",quot:'"',apos:"'",lt:"<",gt:">",middot:"·",hellip:"…",ndash:"–",mdash:"—"};
  let result = value;
  for (let pass = 0; pass < 2; pass += 1) {
    result = result.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (match, entity: string) => {
      const key = entity.toLowerCase();
      if (!key.startsWith("#")) return entities[key] ?? match;
      const point = Number.parseInt(key.slice(key.startsWith("#x") ? 2 : 1), key.startsWith("#x") ? 16 : 10);
      return point >= 32 && point <= 0x10ffff && !(point >= 0xd800 && point <= 0xdfff) ? String.fromCodePoint(point) : match;
    });
  }
  return result.replace(/\s+/gu, " ").trim();
}

export function assessHomepagePublication(item: HomepagePublicationCandidate): HomepageAdmission {
  const title = normalizeHomepageText(item.title).normalize("NFKC");
  if (!title) return {admitted:false,reason:"missing-title",correctedType:null};
  try {
    const url = new URL(item.source.url);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password) throw new Error("unsafe");
  } catch { return {admitted:false,reason:"invalid-source",correctedType:null}; }
  // Suppress narrow, non-event patterns on the research feed; retain the archive.
  // Fundraising, acquisitions and operational disclosures must remain eligible.
  if (/主力资金净(买入|卖出)|^(港股|A股|沪深|美股|大盘)(收评|午评|早评)[:：]/u.test(title) ||
      (/ETF/iu.test(title) && /获资金持续加码|资金净流入|资金净买入/u.test(title))) {
    return {admitted:false,reason:"routine-market-trading",correctedType:null};
  }
  const source = new URL(item.source.url);
  if (/(^|\.)straitsresearch\.com$/iu.test(source.hostname) && /\/report\//u.test(source.pathname) && /市场规模.*份额.*增长/u.test(title)) {
    return {admitted:false,reason:"market-report-sales-page",correctedType:null};
  }
  // Require BOTH signals. A satellite constellation or astronomical discovery
  // must not be confused with fortune/relationship content. Metadata cannot
  // rescue a plainly unrelated title by tagging it AI or energy.
  if (/(星座|生肖|水瓶座|双鱼座|白羊座|金牛座|双子座|巨蟹座|狮子座|处女座|天秤座|天蝎座|射手座|摩羯座)/u.test(title) &&
      /(运势|桃花运|最容易显得笨|天生.*性格|天生.*有钱|最.*花心|最.*痴情)/u.test(title) &&
      !/(辟谣|伪科学|心理学研究|认知偏差|科学检验)/u.test(title)) {
    return {admitted:false,reason:"unrelated-fortune-content",correctedType:null};
  }
  if (/^(相关阅读|相关推荐|猜你喜欢|下一篇|上一篇)[:：\s]/u.test(normalizeHomepageText(item.summary))) {
    return {admitted:false,reason:"sidebar-instead-of-summary",correctedType:null};
  }
  if (item.type === "IPO" && /(股份变动月报|月报表|Monthly Return|翌日披露报表)/iu.test(title)) {
    return {admitted:true,reason:"routine-disclosure-not-ipo",correctedType:"监管文件"};
  }
  return {admitted:true,reason:null,correctedType:null};
}

export function admitHomepageEvents<T extends HomepagePublicationCandidate>(items: readonly T[]): T[] {
  return items.flatMap((item) => {
    const decision = assessHomepagePublication(item);
    if (!decision.admitted) return [];
    return [{...item, title:normalizeHomepageText(item.title), summary:normalizeHomepageText(item.summary), type:decision.correctedType ?? item.type}];
  });
}

