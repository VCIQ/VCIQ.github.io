import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("person channel bootstrap is canonicalized before first browser interaction", async () => {
  const homepage = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(
    homepage,
    /const projectedPeopleChannelEvents = projectHomepagePersonDirectoryEvents\([\s\S]*?const peopleChannelEvents = mergeHomepagePersonChannelEvents\(\s*\[\],\s*projectedPeopleChannelEvents,\s*activeArticles,?\s*\);/u,
  );
  assert.doesNotMatch(
    homepage,
    /const peopleChannelEvents = projectHomepagePersonDirectoryEvents\(/u,
  );

  const canonicalization = homepage.indexOf("const peopleChannelEvents = mergeHomepagePersonChannelEvents(");
  const initialPayloadSlice = homepage.indexOf("const initialArticles:");
  assert.ok(canonicalization >= 0);
  assert.ok(initialPayloadSlice > canonicalization);
});
