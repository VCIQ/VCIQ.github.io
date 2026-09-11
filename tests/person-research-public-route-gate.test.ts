import assert from "node:assert/strict";
import test from "node:test";

import { researchPeople } from "../lib/people-data";
import { personResearchQueue } from "../lib/person-research-queue";

const publishedPersonSlugs = new Set(researchPeople.map((person) => person.slug));

test("public Research Agent queue only links to published person routes", () => {
  assert.ok(personResearchQueue.queue.length > 0);
  assert.ok(
    personResearchQueue.queue.every((item) => publishedPersonSlugs.has(item.personSlug)),
  );
  assert.equal(
    personResearchQueue.queue.some(
      (item) => item.personSlug === "class-presiden-thomas-sonderman",
    ),
    false,
  );
  assert.equal(
    personResearchQueue.queue.some(
      (item) => item.personSlug === "massachusetts-governo-chris-ballance",
    ),
    false,
  );
});
