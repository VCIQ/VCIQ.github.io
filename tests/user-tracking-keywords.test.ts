import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeTrackingConfig,
  validateTrackingKeyword,
} from "../lib/user-tracking";

test("symbolic technologies remain valid and distinct in the runtime compiler", () => {
  const values = ["C", "C++", "C#", ".NET", "NET", "A/B", "AB"];
  for (const value of values) {
    assert.equal(validateTrackingKeyword(value).valid, true, value);
  }

  const config = normalizeTrackingConfig({
    schemaVersion: 1,
    tracks: [
      {
        slug: "programming-languages",
        name: "编程语言",
        enabled: true,
        custom: true,
        keywords: values,
        people: [],
        sampleCompanies: [],
      },
    ],
    listedCompanies: [],
    sources: [],
  });

  assert.deepEqual(config.tracks[0]?.keywords, values);
});
