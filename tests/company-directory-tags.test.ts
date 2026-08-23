import assert from "node:assert/strict";
import test from "node:test";

import { companyDirectoryRelationTags } from "../lib/company-directory-tags";

test("company directory relation tags keep first-seen order without duplicates", () => {
  assert.deepEqual(
    companyDirectoryRelationTags({
      relatedTracks: ["量子计算", "人工智能"],
      relatedTopics: ["量子计算", "大模型"],
      relatedPeople: ["Jungsang Kim", "Peter Chapman"],
    }),
    ["量子计算", "人工智能", "大模型", "Jungsang Kim"],
  );
});
