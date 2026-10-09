/** Small, shared public-surface admission rules. Never import the full archive here. */
export type HomepagePublicationCandidate = { title: string; summary: string; type: string; source: {url: string}; qualityStatus?: string; };
export type HomepageAdmission = { admitted: boolean; reason: string | null; correctedType: string | null; };
export function assessHomepagePublication(item: HomepagePublicationCandidate): HomepageAdmission {
  const title = item.title.normalize("NFKC").trim();
  if (!title) return {admitted:false,reason:"missing-title",correctedType:null};
  try {
    const url = new URL(item.source.url);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password) throw new Error("unsafe");
  } catch { return {admitted:false,reason:"invalid-source",correctedType:null}; }
  // Require BOTH signals. A satellite constellation or astronomical discovery
  // must not be confused with fortune/relationship content. Metadata cannot
  // rescue a plainly unrelated title by tagging it AI or energy.
  if (/(星座|生肖|水瓶座|双鱼座|白羊座|金牛座|双子座|巨蟹座|狮子座|处女座|天秤座|天蝎座|射手座|摩羯座)/u.test(title) &&
      /(运势|桃花运|最容易显得笨|天生.*性格|天生.*有钱|最.*花心|最.*痴情)/u.test(title) &&
      !/(辟谣|伪科学|心理学研究|认知偏差|科学检验)/u.test(title)) {
    return {admitted:false,reason:"unrelated-fortune-content",correctedType:null};
  }
  if (/^(相关阅读|相关推荐|猜你喜欢|下一篇|上一篇)[:：\s]/u.test(item.summary.trim())) {
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
    return [decision.correctedType ? {...item,type:decision.correctedType} : item];
  });
}
