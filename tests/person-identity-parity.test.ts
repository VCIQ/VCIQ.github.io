import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import test from "node:test";

import generated from "../public/data/people.json";
import fixtures from "./fixtures/person-identity-contract.json";
import { normalizeGeneratedPersonIdentity } from "../lib/person-name-normalization";
import { validatePersonIdentity } from "../lib/person-identity-validation";
import { researchPeople } from "../lib/people-data";

test("Python and public TypeScript share normalization, decisions, and rejection reasons", () => {
  const candidates = [...fixtures.map((row) => row.candidate), ...generated.people];
  // Exercise Unicode/ASCII boundaries where Python and ECMAScript regexes differ.
  for (const separator of [" ", "\t", "\ufeff", "\u0085", "\u001c", "张", "é", "_", "-", "İ", "ı", "ſ", "K"]) {
    for (const word of ["CEO", "presiden", "governo", "class", "Classical", "founder", "Chris"]) {
      candidates.push({ name: `John${separator}${word}${separator}Smith`, englishName: "", aliases: [], handles: [] });
    }
  }
  const script = `
import json, sys
from tools.person_identity_contract import normalized_person_identity, validate_generated_person_identity, validate_person_identity
print(json.dumps([{
  "identity": normalized_person_identity(row),
  "rawValidation": validate_person_identity(row),
  "validation": validate_generated_person_identity(row),
} for row in json.load(sys.stdin)], ensure_ascii=False))
`;
  const actual = JSON.parse(execFileSync("python3", ["-c", script], {
    cwd: resolve(import.meta.dirname, ".."), input: JSON.stringify(candidates), encoding: "utf8",
  })) as { identity: { name: string; englishName: string }; rawValidation: unknown; validation: unknown }[];
  assert.equal(actual.length, candidates.length);
  candidates.forEach((candidate, index) => {
    const normalized = normalizeGeneratedPersonIdentity(candidate);
    assert.deepEqual(actual[index].identity, { name: normalized.name, englishName: normalized.englishName }, `normalize ${index}`);
    assert.deepEqual(actual[index].rawValidation, validatePersonIdentity(candidate), `raw validation ${index}`);
    assert.deepEqual(actual[index].validation, validatePersonIdentity(normalized), `generated validation ${index}`);
  });
  fixtures.forEach((row, index) => assert.deepEqual(actual[index].validation, row.expected, row.case));
});

test("regenerated planner and stale-agenda scheduler only allocate publishable people", () => {
  const script = `
import json
from pathlib import Path
from tools.person_research_agent import build_agenda
from tools.person_research_scheduler import build_daily_queue
people = json.loads(Path("public/data/people.json").read_text())
articles = json.loads(Path("public/data/articles.json").read_text())
stale = json.loads(Path("public/data/person_research_agenda.json").read_text())
memory = json.loads(Path("public/data/person_research_outcomes.json").read_text())
agenda = build_agenda(people, articles)
print(json.dumps({
  "agendaSlugs": list(agenda["people"]),
  "queueSlugs": [row["personSlug"] for row in build_daily_queue(agenda, people, memory)["queue"]],
  "staleQueueSlugs": [row["personSlug"] for row in build_daily_queue(stale, people, memory)["queue"]],
}))
`;
  const output = JSON.parse(execFileSync("python3", ["-c", script], {
    cwd: resolve(import.meta.dirname, ".."), encoding: "utf8",
  })) as Record<string, string[]>;
  const published = new Set(researchPeople.map((person) => person.slug));
  for (const [stage, slugs] of Object.entries(output)) {
    assert.ok(slugs.length > 0, stage);
    assert.ok(slugs.every((slug) => published.has(slug)), stage);
    for (const bad of ["class-presiden-thomas-sonderman", "massachusetts-governo-chris-ballance", "person-16c7c9ad4b"]) {
      assert.ok(!slugs.includes(bad), `${stage}: ${bad}`);
    }
  }
});
