const LOW_SIGNAL_PERSON_TITLE_MARKERS = /must watch|watch now|full interview|leaves audience speechless|震惊|炸裂|刷屏|全网热议|重磅突发|重大消息|改变世界|史诗级|颠覆世界|笑了.{0,12}哭了|捅破|聊透|访谈录|附文稿|中英文本|原声配音|双语音|完整版|生肉|搬运|🔥|\ballegedly\b|\bparty\b|\bdinner\b|婚礼|派对|晚宴/iu;

const RESEARCH_ACTION_MARKERS = /发布|推出|上线|开源|研发|研究|论文|模型|技术|产品|量产|交付|合作|任命|卸任|离任|加入|成立|融资|投资|收购|战略|涨价|降价|监管|政策|演讲|访谈|对话|诉讼|起诉|去世|launch(?:ed|es|ing)?|release(?:d|s|ing)?|open[- ]source|research|paper|model|appoint(?:ed|s|ing)?|resign(?:ed|s|ing)?|step(?:ped|s|ping)? aside|join(?:ed|s|ing)?|found(?:ed|s|ing)?|rais(?:e|ed|es|ing)|invest(?:ed|s|ing|ment)|acquir(?:e|ed|es|ing)|strategy|pricing|leadership|lawsuit|su(?:e|ed|es|ing)|dies|died/iu;

const TRUSTED_PERSON_CHANGE_SOURCES = /官方|官网|本人|大学|研究院|实验室|政府|监管|arxiv|sec\b|github|reuters|bloomberg|financial times|wall street journal|wsj\b|new york times|associated press|ap news|bbc|cnn|cnbc|techcrunch|the information|fortune|forbes|tom'?s hardware|ars technica|mit technology review|nature|science|新浪财经|财联社|证券时报|钛媒体|雷峰网|36氪|晚点|界面新闻|第一财经/iu;

export function isLowSignalPersonTitle(title: string) {
  return LOW_SIGNAL_PERSON_TITLE_MARKERS.test(title);
}

export function hasPersonResearchAction(title: string) {
  return RESEARCH_ACTION_MARKERS.test(title);
}

export function isVideoPlatformMaterial(source: string, href: string) {
  return /bilibili|youtube|youtu\.be/i.test(`${source} ${href}`);
}

export function isTrustedPersonChangeSource(source: string, href: string) {
  if (/news\.google\.|wikidata|stocktwits/i.test(`${source} ${href}`)) return false;
  return TRUSTED_PERSON_CHANGE_SOURCES.test(source);
}
