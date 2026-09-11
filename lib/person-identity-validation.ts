import policy from "./person-identity-policy.json";

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

const NON_PERSON_TERMS = new RegExp(policy.patterns.nonPersonTerms, "u");
const TITLE_BLEED = new RegExp(policy.patterns.titleBleed, "iu");
const SENTENCE_PUNCTUATION = new RegExp(policy.patterns.sentencePunctuation, "u");

const PERSON_CHARACTERS = new RegExp(policy.patterns.personCharacters, "iu");
const LATIN_WORDS = new RegExp(policy.patterns.latinWords, "giu");
const WHITESPACE = new RegExp(policy.patterns.whitespace, "gu");

function clean(value: string | undefined) {
  return value?.normalize(policy.normalizationForm).replace(WHITESPACE, " ").trim() ?? "";
}

export function validatePersonIdentity(candidate: PersonIdentityCandidate): PersonIdentityValidation {
  const name = clean(candidate.name);
  const englishName = clean(candidate.englishName);
  if (!name) return { valid: false, reason: "missing-name" };
  if (name.length > policy.maxNameUtf16Units || englishName.length > policy.maxEnglishNameUtf16Units) {
    return { valid: false, reason: "name-too-long" };
  }
  if (!PERSON_CHARACTERS.test(name)) {
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

  const latinWords = name.match(LATIN_WORDS) ?? [];
  if (latinWords.length > policy.maxLatinWords) {
    return { valid: false, reason: "too-many-name-tokens" };
  }

  return { valid: true };
}
