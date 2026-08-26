type GeneratedIdentityShape = {
  name: string;
  englishName: string;
  aliases: string[];
  handles: string[];
};

export type ParsedPersonIdentityLabel = {
  name: string;
  englishName: string;
  handle: string;
};

function clean(value: string): string {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function key(value: string): string {
  return clean(value).toLocaleLowerCase("zh-CN");
}

function unique(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of values) {
    const value = clean(raw);
    const normalized = key(value);
    if (!value || !normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(value);
  }
  return result;
}

function hasCjk(value: string): boolean {
  return /[\u3400-\u9fff]/.test(value);
}

function hasLatin(value: string): boolean {
  return /[A-Za-z\u00c0-\u024f]/.test(value);
}

function splitHandle(raw: string): { label: string; handle: string } {
  const value = clean(raw);
  const match = value.match(/^(.*?)\s+@([A-Za-z0-9_]{1,30})$/);
  if (!match) return { label: value, handle: "" };
  return { label: clean(match[1]), handle: clean(match[2]) };
}

/**
 * Parse person tracking labels without trusting punctuation quality.
 *
 * Supported examples include:
 * - 埃隆·马斯克 @elonmusk
 * - 黄仁勋 (Jensen Huang)
 * - 黄仁勋(Jensen Huang   // missing closing parenthesis
 * - Clément Delangue（克莱门特·德朗格）
 *
 * Parenthetical text is treated as a bilingual identity only when one side is
 * CJK and the other contains Latin letters. Role/status parentheticals are left
 * untouched.
 */
export function parsePersonIdentityLabel(raw: string): ParsedPersonIdentityLabel {
  const { label, handle } = splitHandle(raw);
  const match = label.match(/^(.+?)\s*[（(]\s*([^()（）]+?)\s*[)）]?\s*$/);
  if (match) {
    const left = clean(match[1]);
    const right = clean(match[2]);
    if (left && right) {
      if (hasCjk(left) && hasLatin(right) && !hasCjk(right)) {
        return { name: left, englishName: right, handle };
      }
      if (hasLatin(left) && !hasCjk(left) && hasCjk(right)) {
        return { name: right, englishName: left, handle };
      }
    }
  }

  return {
    name: label,
    englishName: hasLatin(label) && !hasCjk(label) ? label : "",
    handle,
  };
}

export function normalizeGeneratedPersonIdentity<T extends GeneratedIdentityShape>(person: T): T {
  const primary = parsePersonIdentityLabel(person.name);
  const englishField = parsePersonIdentityLabel(person.englishName);
  const parsedAliases = person.aliases.map(parsePersonIdentityLabel);

  const name = primary.name || englishField.name || clean(person.name);
  const englishName =
    primary.englishName
    || englishField.englishName
    || (hasLatin(englishField.name) && !hasCjk(englishField.name) ? englishField.name : "")
    || (hasLatin(name) && !hasCjk(name) ? name : "")
    || clean(person.englishName)
    || name;

  const aliases = unique([
    name,
    englishName,
    primary.name,
    primary.englishName,
    englishField.name,
    englishField.englishName,
    ...parsedAliases.flatMap((item) => [item.name, item.englishName]),
  ]);
  const handles = unique([
    ...person.handles,
    primary.handle,
    englishField.handle,
    ...parsedAliases.map((item) => item.handle),
  ]);

  return {
    ...person,
    name,
    englishName,
    aliases,
    handles,
  };
}
