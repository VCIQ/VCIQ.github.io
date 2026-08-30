import assert from "node:assert/strict";
import test from "node:test";

import { canonicalPublicHttpUrl } from "../lib/public-url";

test("public URL normalization removes crawler slash artifacts and rejects unsafe schemes", () => {
  assert.equal(canonicalPublicHttpUrl("https://groq.com/blog\\"), "https://groq.com/blog");
  assert.equal(canonicalPublicHttpUrl(" https://example.com/path "), "https://example.com/path");
  assert.equal(canonicalPublicHttpUrl("javascript:alert(1)"), "");
  assert.equal(canonicalPublicHttpUrl("not a url"), "");
});
