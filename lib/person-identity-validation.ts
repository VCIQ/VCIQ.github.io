export type PersonIdentityCandidate = {
  slug?: string;
  name?: string;
  englishName?: string;
  role?: string;
};

export type PersonIdentityValidation = {
  valid: boolean;
  reason?: string;
};

const NON_PERSON_TERMS = /(?:模型|算法|架构|平台|系统|芯片|机器人|半导体|研究院|实验室|大学|学院|公司|集团|基金|委员会|协会|中心|政府|部门|证券|科技)/u;
const TITLE_BLEED = /\b(?:ceo|cto|cfo|presiden\w*|governo\w*|founder|chairman|professor|minister|senator|class|university|institute|laboratory|committee|government|company|group|fund)\b/iu;
const SENTENCE_PUNCTUATION = /[：:；;！？!?。]|(?:\s[-–—]\s)/u;

function clean(value: string | undefined) {
  return value?.normalize("NFKC").replace(/\s+/gu, " ").trim() ?? "";
}

export function validatePersonIdentity(candidate: PersonIdentityCandidate): PersonIdentityValidation {
  const name = clean(candidate.name);
  const englishName = clean(candidate.englishName);
  if (!name) return { valid: false, reason: "missing-name" };
  if (name.length > 72 || englishName.length > 96) {
    return { valid: false, reason: "name-too-long" };
  }
  if (!/[a-z\u3400-\u9fff]/iu.test(name)) {
    return { valid: false, reason: "name-has-no-person-characters" };
  }
  if (NON_PERSON_TERMS.test(name)) {
    return { valid: false, reason: "non-person-entity-term" };
  }
  if (TITLE_BLEED.test(name) || TITLE_BLEED.test(englishName)) {
    return { valid: false, reason: "title-or-organization-bleed" };
  }
  if (SENTENCE_PUNCTUATION.test(name)) {
    return { valid: false, reason: "sentence-like-name" };
  }

  const latinWords = name.match(/[a-z][a-z.'’-]*/giu) ?? [];
  if (latinWords.length > 6) {
    return { valid: false, reason: "too-many-name-tokens" };
  }

  return { valid: true };
}
