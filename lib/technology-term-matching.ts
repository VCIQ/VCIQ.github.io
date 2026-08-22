export function normalizeTechnologyTerm(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function normalizedSearchText(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("zh-CN");
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function asciiBoundaryPattern(rawTerm: string) {
  const pieces = rawTerm.split(/[^a-z0-9]+/iu).filter(Boolean);
  if (!pieces.length) return null;
  const body = pieces.map(escapeRegExp).join("[\\s._:/+\\-]+");
  return new RegExp(`(^|[^a-z0-9])${body}([^a-z0-9]|$)`, "iu");
}

function hasAiModelContext(corpus: string) {
  const text = normalizedSearchText(corpus);
  return (
    /(^|[^a-z0-9])(?:ai|llm|vlm|model|models|vision|language|generative)([^a-z0-9]|$)/iu.test(text) ||
    /模型|大模型|视觉|語言|语言|图像|圖像|视频|視頻|生成式/u.test(corpus)
  );
}

export function technologyTermMatchesText(corpus: string, term: string) {
  const normalizedTerm = normalizeTechnologyTerm(term);
  if (normalizedTerm.length < 2) return false;

  const rawTerm = normalizedSearchText(term).trim();
  const searchText = normalizedSearchText(corpus);

  // Case carries technical meaning for these semiconductor abbreviations. In
  // particular, GaN must not collapse into GAN, and editorial "[sic]" must not
  // become silicon carbide.
  if (term === "GaN") {
    return /(^|[^A-Za-z0-9])GaN([^A-Za-z0-9]|$)/u.test(corpus);
  }
  if (term === "SiC") {
    return /(^|[^A-Za-z0-9])SiC([^A-Za-z0-9]|$)/u.test(corpus);
  }

  // "multimodal" is common in transport, logistics and healthcare prose. It
  // only denotes the model topic when nearby text also establishes AI/model
  // semantics.
  if (rawTerm === "multimodal") {
    return (
      /(^|[^a-z0-9])multimodal([^a-z0-9]|$)/iu.test(searchText) &&
      hasAiModelContext(corpus)
    );
  }

  // Technical identifiers containing separators (2.5D, 3D IC, AI-RAN,
  // world-model, self-driving, etc.) must preserve token structure. Stripping
  // punctuation used to make "MiMo-V2.5 DeepSeek" look like "2.5D".
  if (/^[a-z0-9][a-z0-9\s._:/+\-]*$/iu.test(rawTerm) && /[^a-z0-9]/iu.test(rawTerm)) {
    return asciiBoundaryPattern(rawTerm)?.test(searchText) ?? false;
  }

  const shortAsciiToken = /^[a-z0-9]+$/u.test(rawTerm) && rawTerm.length <= 3;
  if (shortAsciiToken) {
    const tokenPattern = new RegExp(
      `(^|[^a-z0-9])${escapeRegExp(rawTerm)}([^a-z0-9]|$)`,
      "iu",
    );
    return tokenPattern.test(searchText);
  }

  return normalizeTechnologyTerm(corpus).includes(normalizedTerm);
}
